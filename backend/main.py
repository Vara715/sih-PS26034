"""
FastAPI Server Entry Point
--------------------------
Legal Metrology (Packaged Commodities) Compliance Platform API (SIH26034)
"""

import uuid
import sys
import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional

# Adjust Python module path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cv.quality import assess_image_quality
from cv.product_validator import validate_product_image
from ocr.engine import extract_text_from_image
from extraction.extractor import extract_declarations
from rules.engine import evaluate_compliance, load_legal_rules
from database.db import (
    save_inspection, get_all_inspections, get_inspection_by_id, clear_all_inspections, init_db,
    create_user, authenticate_user
)

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
    version="1.0.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database tables on start
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

    if file_back:
        image_bytes_back = await file_back.read()

    # Direct Text Input Mode (Demo / Manual correction)
    if not image_bytes and raw_text_input:
        image_bytes = raw_text_input.encode("utf-8")
        input_validation = validate_product_image(image_bytes)

        if not input_validation["should_proceed_to_ocr"]:
            verdict_title = "INVALID PRODUCT IMAGE / DOCUMENT REJECTED" if input_validation["status"] == "INVALID_PRODUCT_IMAGE" else "IMAGE REQUIRES VERIFICATION"
            
            response_payload = {
                "inspection_id": inspection_id,
                "user_mode": user_mode,
                "product_category": product_category,
                "input_validation": input_validation,
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

        quality_assessment = {
            "is_valid_image": True,
            "is_readable": True,
            "blur_score": 150.0,
            "brightness_score": 128.0,
            "quality_rating": "EXCELLENT",
            "issues": [],
            "message": "Direct label text evaluation mode (Demo)."
        }
        ocr_result = {
            "success": True,
            "full_text": raw_text_input,
            "lines": [line.strip() for line in raw_text_input.splitlines() if line.strip()],
            "confidence": 0.95,
            "engine": "TextDirectInput"
        }
    elif image_bytes:
        # =========================================================================
        # GATE 1: PRODUCT IMAGE PACKAGING EVIDENCE GATE (MUST RUN BEFORE OCR)
        # =========================================================================
        input_validation = validate_product_image(image_bytes)

        input_validation_back = None
        if image_bytes_back:
            input_validation_back = validate_product_image(image_bytes_back)

        # Log diagnostic evidence check
        print(f"[IMAGE_VALIDATION] ID={inspection_id} | Status={input_validation['status']} | "
              f"Score={input_validation['confidence']} | OCR_Executed={input_validation['should_proceed_to_ocr']} | "
              f"Reason={input_validation['reason']}")

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
        # GATE 2: IMAGE QUALITY CHECK (Blur, Brightness, Resolution)
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
            print(f"[IMAGE_QUALITY_GATE] ID={inspection_id} | Rating={quality_assessment.get('quality_rating')} | Blocked")
            
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

    else:
        raise HTTPException(status_code=400, detail="Please upload a package image or provide label text.")

    # 4. Information Extraction (Spatially-aware token evidence engine)
    extracted_declarations = extract_declarations(ocr_result["full_text"], tokens=ocr_result.get("tokens", []))

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
        "user": user
    }


@app.get("/api/inspections")
async def list_inspections(limit: int = 50, role: Optional[str] = "inspector"):
    """Returns recent inspection audit ledger records. Restricted to Legal Metrology Officers."""
    if role and role.lower() not in ["inspector", "officer"]:
        raise HTTPException(status_code=403, detail="Access Forbidden: Only authorized Legal Metrology Officers can view the Audit Ledger Database.")

    history = get_all_inspections(limit=limit)
    return {"inspections": history, "count": len(history)}


@app.delete("/api/inspections")
async def clear_inspections(role: Optional[str] = "inspector"):
    """Clears all audit ledger inspection history records."""
    if role and role.lower() not in ["inspector", "officer"]:
        raise HTTPException(status_code=403, detail="Access Forbidden: Only authorized Legal Metrology Officers can clear the Audit Ledger Database.")
    
    count = clear_all_inspections()
    return {"success": True, "message": f"Cleared {count} inspection history records from database.", "count": 0}


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
