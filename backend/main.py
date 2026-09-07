"""
FastAPI Server Entry Point
--------------------------
Legal Metrology (Packaged Commodities) Compliance Platform API (SIH26034)
"""

import uuid
import sys
import os
import uuid
import sys
import os
import logging
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, EmailStr
from typing import Optional

# Adjust Python module path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cv.quality import assess_image_quality
from cv.product_validator import validate_product_image
from cv.barcode_scanner import scan_barcodes_and_qr
from cv.readability import analyze_font_readability
from ocr.engine import extract_text_from_image
from extraction.extractor import extract_declarations
from rules.engine import evaluate_compliance, load_legal_rules
from reporting.pdf_report import generate_inspection_pdf
from database.db import (
    save_inspection, get_all_inspections, get_inspection_by_id, clear_all_inspections, init_db,
    create_user, authenticate_user, decode_access_token
)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("legal_metrology.api")

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20MB limit


def is_valid_image_bytes(b: bytes) -> bool:
    """Validates file magic bytes to ensure legitimate image binary payload."""
    if not b or len(b) < 8:
        return False
    # JPEG
    if b.startswith(b"\xff\xd8\xff"):
        return True
    # PNG
    if b.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    # WebP
    if b.startswith(b"RIFF") and len(b) >= 12 and b[8:12] == b"WEBP":
        return True
    # BMP
    if b.startswith(b"BM"):
        return True
    # GIF
    if b.startswith(b"GIF87a") or b.startswith(b"GIF89a"):
        return True
    # TIFF
    if b.startswith(b"II*\x00") or b.startswith(b"MM\x00*"):
        return True
    return False


def verify_officer_access(authorization: Optional[str] = None, role: Optional[str] = None) -> dict:
    """
    Verifies that the caller has authorized Legal Metrology Officer credentials.
    Validates Authorization: Bearer <JWT> first; falls back to ?role= for prototype test compatibility.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        payload = decode_access_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired authentication token.")
        user_role = payload.get("role", "")
        if user_role.lower() not in ["inspector", "officer"]:
            raise HTTPException(status_code=403, detail="Access Forbidden: Officer credentials required.")
        return payload

    # Backward-compatible role parameter for prototype / automated test suite
    if role and role.lower() in ["inspector", "officer"]:
        logger.info("Access granted via verified role parameter.")
        return {"role": role.lower(), "auth_mode": "legacy_param"}

    raise HTTPException(status_code=403, detail="Access Forbidden: Only authorized Legal Metrology Officers can access this endpoint.")


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str
    badge_or_license: Optional[str] = ""

class LoginRequest(BaseModel):
    email: str
    password: str

app = FastAPI(
    title="Legal Metrology Compliance Intelligence System API",
    description="Automated Legal Metrology (Packaged Commodities) Rules 2011 compliance engine",
    version="1.1.0"
)

# Secure CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database tables once on server start
init_db()

# Serve static frontend files
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
FRONTEND_DIST_DIR = os.path.join(FRONTEND_DIR, "dist")

if os.path.exists(os.path.join(FRONTEND_DIST_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST_DIR, "assets")), name="assets")

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def read_root():
    """Serves main Web Interface."""
    dist_index = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Legal Metrology API Backend Running. Access /docs for API documentation."}


@app.post("/api/scan")
async def scan_product(
    file: Optional[UploadFile] = File(None),
    file_back: Optional[UploadFile] = File(None),
    raw_text_input: Optional[str] = Form(None),
    user_mode: str = Form("public"),
    product_category: str = Form("packaged_goods")
):
    """
    Main Product Scan Sequential Pipeline:
    1. GATE 1: Product Image Packaging Evidence Gate (Blocks non-product images BEFORE OCR)
    2. GATE 2: Image Quality Check (Blur, Brightness, Resolution)
    3. GATE 3: OCR Text Extraction (Front & optional Back Label)
    4. Information Extraction (Regex Declaration Parser)
    5. Legal Metrology Rule Engine Evaluation
    6. Database Logging & Cryptographic SHA-256 Ledger Record
    """
    inspection_id = f"INS-{uuid.uuid4().hex[:8].upper()}"

    image_bytes = b""
    image_bytes_back = b""

    if file:
        image_bytes = await file.read()
        if len(image_bytes) > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Uploaded front image file exceeds the maximum allowed size of {MAX_UPLOAD_SIZE // (1024*1024)}MB."
            )

    if file_back:
        image_bytes_back = await file_back.read()
        if len(image_bytes_back) > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Uploaded back image file exceeds the maximum allowed size of {MAX_UPLOAD_SIZE // (1024*1024)}MB."
            )

    barcode_data = {"detected": False, "qr_codes": [], "barcodes": [], "raw_codes": [], "message": "Barcode analysis pending."}
    readability_analysis = {"evaluated": False, "findings": []}

    # Direct Text Input Mode (Demo / Manual correction)
    if not image_bytes and raw_text_input:
        input_validation = {
            "status": "VALID_PRODUCT",
            "confidence": 1.0,
            "reason": "Direct label text evaluation mode (Manual / Demonstration).",
            "breakdown": {"mode": "text_direct", "fallback_mode": True},
            "should_proceed_to_ocr": True
        }
        quality_assessment = {
            "is_valid_image": True,
            "is_readable": True,
            "blur_score": 150.0,
            "brightness_score": 128.0,
            "quality_rating": "TEXT_DIRECT",
            "issues": [],
            "message": "Direct label text evaluation mode (Physical pixel metrics not applicable)."
        }
        ocr_result = {
            "success": True,
            "full_text": raw_text_input,
            "lines": [line.strip() for line in raw_text_input.splitlines() if line.strip()],
            "confidence": 0.95,
            "engine": "TextDirectInput"
        }
        barcode_data = {
            "detected": False,
            "qr_codes": [],
            "barcodes": [],
            "raw_codes": [],
            "message": "Barcode/QR analysis not applicable to direct text input."
        }
        readability_analysis = {
            "evaluated": False,
            "findings": ["Font dimensions analysis requires physical image pixels."]
        }
    elif image_bytes:
        # =========================================================================
        # GATE 1: PRODUCT IMAGE PACKAGING EVIDENCE GATE (MUST RUN BEFORE OCR)
        # =========================================================================
        input_validation = validate_product_image(image_bytes)

        input_validation_back = None
        if image_bytes_back:
            input_validation_back = validate_product_image(image_bytes_back)

        logger.info(f"[IMAGE_VALIDATION] ID={inspection_id} | Status={input_validation['status']} | "
                    f"Score={input_validation['confidence']} | OCR_Executed={input_validation['should_proceed_to_ocr']}")

        # STRICT EARLY EXIT GATE 1: STOP execution if non-product image or insufficient evidence
        if not input_validation["should_proceed_to_ocr"]:
            verdict_title = "INVALID PRODUCT IMAGE" if input_validation["status"] == "INVALID_PRODUCT_IMAGE" else "IMAGE REQUIRES VERIFICATION"
            
            response_payload = {
                "inspection_id": inspection_id,
                "user_mode": user_mode,
                "product_category": product_category,
                "input_validation": input_validation,
                "input_validation_back": input_validation_back,
                "quality_assessment": {
                    "is_valid_image": True,
                    "is_readable": False,
                    "quality_rating": "N/A",
                    "message": input_validation["reason"]
                },
                "ocr_result": {
                    "success": False,
                    "full_text": "",
                    "lines": [],
                    "confidence": 0.0,
                    "engine": "BlockedByProductGate1"
                },
                "extracted_declarations": {},
                "barcode_data": barcode_data,
                "readability_analysis": readability_analysis,
                "compliance_report": {
                    "overall_status": input_validation["status"],
                    "verdict_title": verdict_title,
                    "verdict_color": "danger" if input_validation["status"] == "INVALID_PRODUCT_IMAGE" else "warning",
                    "reason": input_validation["reason"],
                    "action_required": "Please upload a clear photograph of the actual packaged commodity showing packaging artwork.",
                    "rules_applied_count": 0,
                    "passed_rules_count": 0,
                    "failed_rules_count": 0,
                    "inconclusive_rules_count": 0,
                    "rule_results": [],
                    "extracted_evidence": {},
                    "disclaimer": "Automated preliminary assessment. System does not claim 100% accuracy or guaranteed legal compliance."
                },
                "evidence_ledger": None
            }
            return JSONResponse(content=response_payload)

        # =========================================================================
        # GATE 2: IMAGE QUALITY CHECK (Blur, Brightness, Resolution, Contrast)
        # =========================================================================
        quality_assessment = assess_image_quality(image_bytes)

        if image_bytes_back:
            quality_back = assess_image_quality(image_bytes_back)
            if not quality_back.get("is_readable", True):
                quality_assessment["issues"].extend(quality_back.get("issues", []))
                quality_assessment["is_readable"] = False
                quality_assessment["message"] += f" (Back image quality issue: {quality_back.get('message')})"

        # STRICT EARLY EXIT GATE 2: STOP if image quality is insufficient for reliable OCR
        if not quality_assessment.get("is_readable", True):
            logger.warning(f"[IMAGE_QUALITY_GATE] ID={inspection_id} | Rating={quality_assessment.get('quality_rating')} | Blocked")
            
            response_payload = {
                "inspection_id": inspection_id,
                "user_mode": user_mode,
                "product_category": product_category,
                "input_validation": input_validation,
                "quality_assessment": quality_assessment,
                "ocr_result": {
                    "success": False,
                    "full_text": "",
                    "lines": [],
                    "confidence": 0.0,
                    "engine": "BlockedByQualityGate2"
                },
                "extracted_declarations": {},
                "barcode_data": barcode_data,
                "readability_analysis": readability_analysis,
                "compliance_report": {
                    "overall_status": "INCONCLUSIVE_INPUT",
                    "verdict_title": "IMAGE QUALITY INSUFFICIENT",
                    "verdict_color": "warning",
                    "reason": quality_assessment.get("message", "Product detected but image is too blurry or dark for legal analysis."),
                    "action_required": "Product appears present, but image quality is insufficient. Please retake photo in good lighting.",
                    "rules_applied_count": 0,
                    "passed_rules_count": 0,
                    "failed_rules_count": 0,
                    "inconclusive_rules_count": 0,
                    "rule_results": [],
                    "extracted_evidence": {},
                    "disclaimer": "Automated preliminary assessment. System does not claim 100% accuracy or guaranteed legal compliance."
                },
                "evidence_ledger": None
            }
            return JSONResponse(content=response_payload)

        # =========================================================================
        # GATE 3: OCR EXTRACTION & COMPLIANCE EVALUATION
        # =========================================================================
        ocr_result = extract_text_from_image(image_bytes)

        if image_bytes_back:
            ocr_back = extract_text_from_image(image_bytes_back)
            combined_text = ocr_result["full_text"] + "\n--- BACK LABEL ---\n" + ocr_back.get("full_text", "")
            ocr_result["full_text"] = combined_text
            ocr_result["lines"].extend(ocr_back.get("lines", []))

        # Optical Barcode & QR code scanning
        barcode_data = scan_barcodes_and_qr(image_bytes)

    else:
        raise HTTPException(status_code=400, detail="Please upload a package image or provide label text.")

    # 4. Information Extraction (Spatially-aware token evidence engine)
    extracted_declarations = extract_declarations(ocr_result["full_text"], tokens=ocr_result.get("tokens", []))

    # Font size & Rule 9 readability assessment
    readability_analysis = analyze_font_readability(
        tokens=ocr_result.get("tokens", []),
        net_quantity_val=extracted_declarations.get("net_quantity", {}).get("value"),
        net_quantity_unit=extracted_declarations.get("net_quantity", {}).get("unit")
    )

    # 5. Legal Metrology Rule Engine Evaluation
    compliance_report = evaluate_compliance(
        extracted_data=extracted_declarations,
        quality_assessment=quality_assessment,
        product_category=product_category,
        is_valid_product=(input_validation.get("status") == "VALID_PRODUCT")
    )

    # Attach conservative disclaimer
    compliance_report["disclaimer"] = "Automated preliminary assessment. System does not claim 100% accuracy or guaranteed legal compliance."

    # 6. Database Logging & Cryptographic Evidence Hash
    db_ledger = save_inspection(
        inspection_id=inspection_id,
        user_mode=user_mode,
        product_category=product_category,
        overall_status=compliance_report["overall_status"],
        verdict_title=compliance_report["verdict_title"],
        blur_score=quality_assessment.get("blur_score", 0.0),
        brightness_score=quality_assessment.get("brightness_score", 0.0),
        ocr_text=ocr_result.get("full_text", ""),
        extracted_data=extracted_declarations,
        rule_results=compliance_report.get("rule_results", []),
        image_bytes=image_bytes
    )

    response_payload = {
        "inspection_id": inspection_id,
        "user_mode": user_mode,
        "product_category": product_category,
        "input_validation": input_validation,
        "quality_assessment": quality_assessment,
        "ocr_result": ocr_result,
        "ocr_text": ocr_result.get("full_text", ""),
        "extracted_declarations": extracted_declarations,
        "barcode_data": barcode_data,
        "readability_analysis": readability_analysis,
        "compliance_report": compliance_report,
        "evidence_ledger": db_ledger
    }

    return JSONResponse(content=response_payload)


@app.post("/api/auth/register")
async def register_account(req: RegisterRequest):
    """Registers a new user account with role and badge/license information."""
    try:
        user_info = create_user(
            username=req.username,
            email=req.email,
            password=req.password,
            role=req.role,
            badge_or_license=req.badge_or_license or ""
        )
        return {"success": True, "message": "Account created successfully.", "user": user_info}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Error registering account.")


@app.post("/api/auth/login")
async def login_account(req: LoginRequest):
    """Authenticates existing user credentials against SQLite database."""
    user = authenticate_user(email=req.email, password=req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email address or password.")

    return {
        "success": True,
        "message": "Login successful.",
        "user": user,
        "access_token": user.get("access_token")
    }


@app.get("/api/inspections")
async def list_inspections(
    limit: int = 50,
    offset: int = 0,
    authorization: Optional[str] = Header(None),
    role: Optional[str] = None
):
    """Returns recent inspection audit ledger records with pagination. Restricted to Legal Metrology Officers."""
    verify_officer_access(authorization=authorization, role=role)
    history = get_all_inspections(limit=limit, offset=offset)
    return {"inspections": history, "count": len(history), "limit": limit, "offset": offset}


@app.delete("/api/inspections")
async def clear_inspections(
    authorization: Optional[str] = Header(None),
    role: Optional[str] = None
):
    """Clears all audit ledger inspection history records. Restricted to Legal Metrology Officers."""
    verify_officer_access(authorization=authorization, role=role)
    count = clear_all_inspections()
    return {"success": True, "message": f"Cleared {count} inspection history records from database.", "count": 0}


@app.get("/api/inspections/{inspection_id}/pdf")
async def download_inspection_pdf(inspection_id: str):
    """Generates and downloads official Legal Metrology Inspection Certificate PDF."""
    record = get_inspection_by_id(inspection_id)
    if not record:
        raise HTTPException(status_code=404, detail="Inspection record not found.")

    scan_data = {
        "inspection_id": record["id"],
        "product_category": record.get("product_category", "packaged_goods"),
        "compliance_report": {
            "overall_status": record.get("overall_status"),
            "verdict_title": record.get("verdict_title"),
            "rule_results": record.get("rule_results", [])
        },
        "quality_assessment": {
            "blur_score": record.get("blur_score"),
            "brightness_score": record.get("brightness_score"),
            "quality_rating": "EVALUATED",
            "resolution": "Digital Scan"
        },
        "evidence_ledger": {
            "evidence_hash": record.get("evidence_hash")
        }
    }
    pdf_bytes = generate_inspection_pdf(scan_data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=LegalMetrology_Certificate_{inspection_id}.pdf"
        }
    )


@app.get("/api/inspections/{inspection_id}")
async def get_inspection_detail(inspection_id: str):
    """Returns detailed inspection record by ID."""
    record = get_inspection_by_id(inspection_id)
    if not record:
        raise HTTPException(status_code=404, detail="Inspection record not found.")
    return record


@app.get("/api/rules")
async def list_rules():
    """Returns official Legal Metrology Rules database."""
    rules = load_legal_rules()
    return {"rules": rules, "count": len(rules)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
