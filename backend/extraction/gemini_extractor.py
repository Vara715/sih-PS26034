"""
Gemini Vision Fallback Extractor & Evidence Reconciliation
----------------------------------------------------------
Provides a secondary visual extraction pass using the Gemini Vision API when the
primary deterministic OCR+regex pipeline returns missing, inconclusive, or low-
confidence evidence for Legal Metrology mandatory declarations.

Architectural invariants:
  1. Gemini is purely a SECONDARY VISUAL EVIDENCE SOURCE.
  2. The deterministic Legal Metrology rule engine remains the sole, final authority
     for COMPLIANT / POTENTIAL NON-COMPLIANCE / INCONCLUSIVE compliance verdicts.
  3. Evidence contract: 'VERIFIED' + 'detected=True' strictly implies that a usable,
     non-null declaration value exists. Missing/null fields are NEVER marked VERIFIED.
  4. Any exception during the Gemini API call is caught and logged; it MUST NEVER
     crash the /api/scan endpoint.
  5. The GEMINI_API_KEY is loaded server-side only and NEVER leaked to API responses.
  6. Automated unit/integration tests must mock Gemini calls (zero quota consumption).
"""

import os
import re
import json
import logging
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("legal_metrology.gemini_extractor")

# ---------------------------------------------------------------------------
# Constants & Model Strategy
# ---------------------------------------------------------------------------

_MANDATORY_FIELDS = [
    "mrp",
    "net_quantity",
    "manufacturing_date",
    "expiry_date",
    "batch_number",
    "unit_sale_price",
    "manufacturer",
    "consumer_care",
    "fssai_license",
    "generic_name",
    "country_of_origin",
]

# Model Hierarchy:
# - Primary verified model: 'gemini-3.6-flash' (fast, robust for visual document extraction)
# - Higher-quality pro model: configurable via GEMINI_VISION_MODEL (e.g. 'gemini-2.5-pro')
# - Fallback default remains 'gemini-3.6-flash'
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"

_GEMINI_PROMPT = """You are an expert Legal Metrology statutory compliance inspector analyzing a photograph of an Indian packaged commodity under the Legal Metrology (Packaged Commodities) Rules, 2011.

INSPECTION INSTRUCTIONS:
1. Thoroughly inspect the ENTIRE package image across all visible sides, panels, and margins (front, back, sides, top, flap, bottom).
2. Locate official mandatory statutory declaration anchors and their associated values:
   - "MRP" / "Maximum Retail Price" / "Incl. of all taxes" -> Extract exact retail price (numeric value and visible text)
   - "Net Qty" / "Net Quantity" / "Net Weight" / "N.W." / "Weight" -> Extract exact visible quantity string with unit (e.g. "24g", "500 ml", "1 kg", "10 N")
   - "MFD" / "Mfg Date" / "Packed" / "PKD" / "Date of Packing" -> Extract exact visible manufacturing date string and anchor
   - "Expiry" / "Use By" / "Best Before" / "BB" -> Extract exact visible expiry/best-before date string and anchor
   - "Batch No" / "Lot No" / "B.No" / "Code No" -> Extract exact batch or lot identification code
   - "Unit Sale Price" / "USP" -> Extract visible unit sale price (e.g. ₹0.20/g) or null if absent
   - "Manufactured by" / "Packed by" / "Mfd by" / "Marketed by" -> Extract visible company name and postal address
   - "Consumer Care" / "Customer Care" / "Toll Free" / "Email" -> Extract helpline phone, email, and/or address
   - "FSSAI" / "Lic. No." -> Extract 14-digit FSSAI license number
   - "Product" / "Generic Name" / "Commodity" -> Extract exact generic/common commodity name declared on label
   - "Country of Origin" / "Made in" / "Product of" -> Extract declared country of origin or null if not declared

STRICT LEGAL EVIDENCE RULES:
- Report ONLY what is LITERALLY VISIBLE on the packaging artwork.
- Do NOT guess, infer, calculate, or hallucinate any values.
- Do NOT use barcode number to invent details not printed in plain text.
- If a declaration is missing, partially obscured, or unreadable, set value to null.
- Set "visible_text" to the exact character sequence seen on the package including anchor text.

Return ONLY a single valid JSON object matching this schema (no markdown fences, no explanatory prose):
{
  "mrp": {
    "value": <number or null>,
    "visible_text": "<exact text seen or null>"
  },
  "net_quantity": {
    "value": "<exact quantity string e.g. '24g' or null>",
    "visible_text": "<exact text seen or null>"
  },
  "manufacturing_date": {
    "value": "<exact date string e.g. '29AUG26' or '08/2026' or null>",
    "visible_text": "<exact text seen or null>"
  },
  "expiry_date": {
    "value": "<exact date string e.g. '28DEC26' or '08/2027' or null>",
    "visible_text": "<exact text seen or null>"
  },
  "batch_number": {
    "value": "<exact batch string e.g. '1/U1N29D' or null>",
    "visible_text": "<exact text seen or null>"
  },
  "unit_sale_price": {
    "value": <number or null>,
    "visible_text": "<exact text seen or null>"
  },
  "manufacturer": {
    "value": "<exact visible company name and address or null>",
    "visible_text": "<exact text seen or null>"
  },
  "consumer_care": {
    "value": "<exact phone number, email, or contact text or null>",
    "visible_text": "<exact text seen or null>"
  },
  "fssai_license": {
    "value": "<exact 14-digit FSSAI number or null>",
    "visible_text": "<exact text seen or null>"
  },
  "generic_name": {
    "value": "<exact generic commodity name or null>",
    "visible_text": "<exact text seen or null>"
  },
  "country_of_origin": {
    "value": "<exact country name or null>",
    "visible_text": "<exact text seen or null>"
  }
}"""


# ---------------------------------------------------------------------------
# Client & Configuration Management
# ---------------------------------------------------------------------------

def _get_gemini_client():
    """Returns a configured Gemini Client or raises ImportError/ValueError."""
    try:
        from google import genai
    except ImportError as e:
        raise ImportError("google-genai package is not installed.") from e

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")

    return genai.Client(api_key=api_key)


def _get_gemini_model() -> str:
    """Returns the configured Gemini vision model name from env or falls back to default."""
    return os.environ.get("GEMINI_VISION_MODEL", DEFAULT_GEMINI_MODEL).strip()


# ---------------------------------------------------------------------------
# Image Optimization (Call Efficiency without quality loss)
# ---------------------------------------------------------------------------

def _optimize_image_bytes(image_bytes: bytes, max_dim: int = 1600) -> tuple[bytes, str]:
    """
    Optimizes oversized package images before network transmission to Gemini API.
    Reduces transmission payload and latency while maintaining sharp text fidelity.
    """
    mime = _detect_mime(image_bytes)
    if len(image_bytes) <= 1_200_000:
        return image_bytes, mime

    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size
        if max(w, h) > max_dim:
            scale = max_dim / float(max(w, h))
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=85, optimize=True)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:
        logger.debug(f"[GEMINI] Image resize skipped: {e}")
        return image_bytes, mime


def _detect_mime(image_bytes: bytes) -> str:
    """Detects image MIME type from binary magic bytes."""
    if not image_bytes or len(image_bytes) < 4:
        return "image/jpeg"
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:4] == b"RIFF" and len(image_bytes) >= 12 and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    if image_bytes[:2] == b"BM":
        return "image/bmp"
    return "image/jpeg"


# ---------------------------------------------------------------------------
# Parsing Helpers
# ---------------------------------------------------------------------------

def _clean_val(val: Any) -> Optional[Any]:
    """Normalizes string/numeric values, converting string nulls to None."""
    if val is None:
        return None
    s = str(val).strip()
    if s.lower() in ("", "none", "null", "n/a", "not available", "unknown", "undefined"):
        return None
    return val


def _parse_mrp_val(val: Any) -> Optional[float]:
    """Parses MRP into a clean float value."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if val > 0 else None
    s = re.sub(r"[^\d.]", "", str(val))
    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


def _parse_qty(val: Any) -> Tuple[Optional[float], Optional[str], bool]:
    """
    Parses a quantity string like '24g', '500 ml', '1 kg' into (value, unit, is_standard_metric).
    """
    if val is None:
        return None, None, True
    if isinstance(val, (int, float)):
        return float(val), "g", True

    s = str(val).strip()
    m = re.search(r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?", s)
    if m:
        try:
            num = float(m.group(1))
            unit = (m.group(2) or "g").lower()
            std_units = {"g", "gm", "gram", "grams", "kg", "ml", "l", "ltr", "litre", "litres", "m", "cm", "mm", "n", "pcs", "piece", "pieces"}
            is_std = unit in std_units
            norm_unit = "g" if unit in ["gm", "gram", "grams"] else ("kg" if unit == "kg" else ("ml" if unit == "ml" else ("l" if unit in ["ltr", "litre", "litres"] else unit)))
            return num, norm_unit, is_std
        except ValueError:
            pass
    return None, None, True


def _values_agree(val_a: Any, val_b: Any) -> bool:
    """
    Conservative agreement check between OCR value and Gemini value.
    - Compares numeric amounts within 5% tolerance.
    - Compares alphanumeric strings after punctuation/case normalization.
    """
    if val_a is None or val_b is None:
        return False

    # 1. Try numeric comparison
    try:
        clean_a = re.sub(r"[^\d.]", "", str(val_a))
        clean_b = re.sub(r"[^\d.]", "", str(val_b))
        if clean_a and clean_b:
            num_a = float(clean_a)
            num_b = float(clean_b)
            if num_a == 0 and num_b == 0:
                return True
            if num_a > 0 and num_b > 0:
                diff = abs(num_a - num_b) / max(num_a, num_b)
                if diff <= 0.05:
                    return True
    except (ValueError, TypeError):
        pass

    # 2. String comparison (alphanumeric normalized)
    str_a = re.sub(r"[\W_]+", "", str(val_a).lower())
    str_b = re.sub(r"[\W_]+", "", str(val_b).lower())
    if not str_a or not str_b:
        return False
    if str_a == str_b or str_a in str_b or str_b in str_a:
        return True

    return False


# ---------------------------------------------------------------------------
# Trigger Logic
# ---------------------------------------------------------------------------

def should_call_gemini(ocr_declarations: dict) -> tuple[bool, str]:
    """
    Determines whether Gemini should be called as a secondary fallback.
    Triggers when any mandatory Legal Metrology field is:
      - Completely absent from OCR output
      - Marked detected=False
      - Marked status='INCONCLUSIVE'
      - Has confidence < 0.5
    """
    if not ocr_declarations:
        return True, "No OCR declarations produced"

    weak_fields = []
    for field in _MANDATORY_FIELDS:
        fd = ocr_declarations.get(field)
        if not fd:
            weak_fields.append(f"{field}:missing")
            continue
        if not fd.get("detected", False):
            weak_fields.append(f"{field}:missing")
        elif fd.get("status") == "INCONCLUSIVE":
            weak_fields.append(f"{field}:inconclusive")
        elif isinstance(fd.get("confidence"), (int, float)) and fd["confidence"] < 0.5:
            weak_fields.append(f"{field}:low_conf")

    if weak_fields:
        return True, f"Weak OCR evidence on fields: {', '.join(weak_fields[:5])}"

    return False, "OCR evidence sufficient; Gemini not required"


# ---------------------------------------------------------------------------
# Primary Gemini Vision Extraction
# ---------------------------------------------------------------------------

def extract_with_gemini(
    image_bytes: bytes,
    product_category: str = "packaged_goods"
) -> dict:
    """
    Calls the Gemini Vision API to extract mandatory declaration evidence.
    Returns a dict mapping field names to structured evidence objects:
      {
        "mrp": {"value": 5.0, "visible_text": "MRP Rs. 5.00", "confidence": 0.85, "source": "gemini"},
        ...
      }
    Non-fatal: on ANY error, returns {} and logs safely. Never raises.
    """
    result: dict = {}

    try:
        client = _get_gemini_client()
        model_name = _get_gemini_model()

        opt_bytes, mime = _optimize_image_bytes(image_bytes)

        from google.genai import types as genai_types

        image_part = genai_types.Part.from_bytes(
            data=opt_bytes,
            mime_type=mime,
        )

        # Build clean config; explicitly disable AFC to avoid SDK warning
        config_kwargs: Dict[str, Any] = {
            "response_mime_type": "application/json",
            "temperature": 0.0,
            "max_output_tokens": 4096,
        }
        if hasattr(genai_types, "AutomaticFunctionCallingConfig"):
            config_kwargs["automatic_function_calling"] = genai_types.AutomaticFunctionCallingConfig(disable=True)

        response = client.models.generate_content(
            model=model_name,
            contents=[image_part, _GEMINI_PROMPT],
            config=genai_types.GenerateContentConfig(**config_kwargs),
        )

        raw_text = response.text or ""
        parsed = _parse_gemini_response(raw_text)

        for field, data in parsed.items():
            if field not in _MANDATORY_FIELDS:
                continue
            if not isinstance(data, dict):
                continue
            val = _clean_val(data.get("value"))
            vis = _clean_val(data.get("visible_text"))
            if val is None:
                continue

            result[field] = {
                "value": val,
                "visible_text": str(vis or val),
                "raw_text": str(vis or val),
                "confidence": 0.85,
                "source": "gemini",
            }

        logger.info(
            f"[GEMINI] Extracted {len(result)}/{len(_MANDATORY_FIELDS)} fields "
            f"from image ({len(image_bytes)} bytes), model={model_name}"
        )

    except ImportError as e:
        logger.warning(f"[GEMINI] google-genai SDK not available: {e}")
    except ValueError as e:
        logger.warning(f"[GEMINI] Configuration error: {e}")
    except Exception as e:
        logger.error(f"[GEMINI] Unexpected non-fatal error during vision extraction: {e}")

    return result


def _parse_gemini_response(raw_text: str) -> dict:
    """Parses raw text response from Gemini into a dictionary, stripping code fences."""
    if not raw_text:
        return {}

    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = []
        in_block = False
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            if line.startswith("```") and in_block:
                break
            if in_block:
                inner.append(line)
        text = "\n".join(inner).strip()

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError as e:
        logger.warning(f"[GEMINI] JSON decode error: {e}. Raw preview: {raw_text[:120]!r}")
        return {}


# ---------------------------------------------------------------------------
# Conservative Evidence Fusion (4 Cases)
# ---------------------------------------------------------------------------

def fuse_gemini_evidence(ocr_declarations: dict, gemini_fields: dict) -> dict:
    """
    Merges Gemini visual evidence into the OCR declaration dictionary using 4-case logic:

    Case A: OCR strong valid evidence + Gemini agrees
            -> Corroborates evidence; source='ocr+gemini'; confidence boosted modestly.
    Case B: OCR missing / null value / INCONCLUSIVE + Gemini found clear value
            -> Populates field with Gemini evidence; status='VERIFIED'; source='gemini'; fusion_case='B'.
    Case C: OCR strong valid evidence + Gemini differs
            -> Flags conflict; status='INCONCLUSIVE'; conflict=True; preserves both values.
    Case D: Gemini returned null / no usable value
            -> Leaves OCR evidence unchanged.

    Returns a new fused dictionary without mutating input objects.
    """
    fused = {k: dict(v) if isinstance(v, dict) else v for k, v in ocr_declarations.items()}

    for field, gemini_data in gemini_fields.items():
        gemini_val = _clean_val(gemini_data.get("value"))
        if gemini_val is None:
            # Case D: Gemini cannot read this field
            continue

        ocr_fd = fused.get(field, {})
        ocr_detected = bool(ocr_fd.get("detected", False))
        ocr_val = _clean_val(ocr_fd.get("value"))
        ocr_status = ocr_fd.get("status", "INCONCLUSIVE")

        # Check if OCR has strong, usable, verified evidence
        ocr_has_usable_evidence = ocr_detected and ocr_val is not None and ocr_status == "VERIFIED"

        if not ocr_has_usable_evidence:
            # Case B: OCR missing, inconclusive, or null value -> Gemini fills evidence
            logger.debug(f"[FUSION] Case B — Gemini fills field '{field}': {gemini_val}")
            vis_text = gemini_data.get("visible_text") or str(gemini_val)

            new_fd = {
                **ocr_fd,
                "detected": True,
                "value": gemini_val,
                "visible_text": vis_text,
                "raw_text": vis_text,
                "confidence": gemini_data.get("confidence", 0.85),
                "status": "VERIFIED",
                "source": "gemini",
                "fusion_case": "B",
                "evidence_reason": f"Visually verified from package label artwork via Gemini Vision: '{vis_text}'."
            }

            # Map field-specific keys to ensure rule engine compatibility
            if field == "mrp":
                parsed_mrp = _parse_mrp_val(gemini_val)
                new_fd["value"] = parsed_mrp if parsed_mrp is not None else gemini_val
                new_fd["currency"] = "INR"
                new_fd["has_taxes_clause"] = True
            elif field == "net_quantity":
                qv, qu, qs = _parse_qty(gemini_val)
                new_fd["value"] = qv if qv is not None else gemini_val
                new_fd["unit"] = qu or "g"
                new_fd["is_standard_metric"] = qs
            elif field == "manufacturing_date":
                new_fd["date_str"] = str(gemini_val)
                new_fd["is_valid"] = True
            elif field == "expiry_date":
                new_fd["date_str"] = str(gemini_val)
                new_fd["is_valid"] = True
            elif field == "manufacturer":
                new_fd["details"] = str(gemini_val)
            elif field == "consumer_care":
                sval = str(gemini_val)
                if "@" in sval:
                    new_fd["email"] = sval
                if any(c.isdigit() for c in sval):
                    new_fd["phone"] = sval
            elif field == "country_of_origin":
                new_fd["country"] = str(gemini_val)
            elif field == "generic_name":
                new_fd["name"] = str(gemini_val)
            elif field == "fssai_license":
                new_fd["license_number"] = str(gemini_val)
            elif field == "batch_number":
                new_fd["batch_number"] = str(gemini_val)

            fused[field] = new_fd

        else:
            # Both OCR and Gemini have a value — compare them
            if _values_agree(ocr_val, gemini_val):
                # Case A: Agreement -> Corroboration
                logger.debug(f"[FUSION] Case A — OCR+Gemini corroborate on '{field}': OCR={ocr_val!r} vs Gem={gemini_val!r}")
                curr_conf = float(ocr_fd.get("confidence", 0.75))
                fused[field] = {
                    **ocr_fd,
                    "confidence": min(1.0, round(curr_conf + 0.15, 2)),
                    "source": "ocr+gemini",
                    "fusion_case": "A",
                    "gemini_verified": True,
                    "gemini_value": gemini_val,
                }
            else:
                # Case C: Conflict -> Mark INCONCLUSIVE
                logger.warning(
                    f"[FUSION] Case C — CONFLICT on '{field}': "
                    f"OCR='{ocr_val}' vs Gemini='{gemini_val}'"
                )
                fused[field] = {
                    **ocr_fd,
                    "status": "INCONCLUSIVE",
                    "conflict": True,
                    "conflict_detail": f"OCR detected '{ocr_val}' but Gemini vision read '{gemini_val}'",
                    "source": "ocr (conflict with gemini)",
                    "fusion_case": "C",
                    "ocr_value": ocr_val,
                    "gemini_value": gemini_val,
                }

    return fused


# ---------------------------------------------------------------------------
# Evidence Contract Normalization
# ---------------------------------------------------------------------------

def normalize_declaration_evidence(declarations: dict) -> dict:
    """
    Enforces the strict Evidence Contract across all declaration fields:

    INVARIANTS ENFORCED:
    1. 'status=VERIFIED' and 'detected=True' STRICTLY REQUIRES a non-null, usable value.
       Any field with null/empty value that is marked VERIFIED is corrected to INCONCLUSIVE.
    2. 'raw_text' and 'visible_text' are always populated if a usable value exists.
    3. All field-specific aliases (e.g. details, date_str, country, name, license_number)
       are synchronized with 'value'.
    4. Provenance defaults: source='ocr', conflict=False.
    """
    if not isinstance(declarations, dict):
        return {}

    normalized: Dict[str, Any] = {}

    for field, fd in declarations.items():
        if not isinstance(fd, dict):
            normalized[field] = fd
            continue

        f = dict(fd)

        # 1. Synchronize field-specific aliases with primary value
        val = _clean_val(f.get("value"))

        if field == "mrp":
            if val is None and f.get("raw_text"):
                val = _parse_mrp_val(f.get("raw_text"))
                f["value"] = val
            elif val is not None:
                f["value"] = _parse_mrp_val(val) or val
        elif field == "net_quantity":
            if val is None and f.get("raw_text"):
                qv, qu, qs = _parse_qty(f.get("raw_text"))
                f["value"] = qv
                f["unit"] = qu
                f["is_standard_metric"] = qs
            elif val is not None and not f.get("unit"):
                _, qu, qs = _parse_qty(val)
                if qu:
                    f["unit"] = qu
                    f["is_standard_metric"] = qs
            val = _clean_val(f.get("value"))
        elif field == "manufacturing_date":
            if val is None:
                val = _clean_val(f.get("date_str"))
                f["value"] = val
            elif not f.get("date_str"):
                f["date_str"] = str(val)
        elif field == "expiry_date":
            if val is None:
                val = _clean_val(f.get("date_str"))
                f["value"] = val
            elif not f.get("date_str"):
                f["date_str"] = str(val)
        elif field == "manufacturer":
            if val is None:
                val = _clean_val(f.get("details"))
                f["value"] = val
            elif not f.get("details"):
                f["details"] = str(val)
        elif field == "consumer_care":
            if val is None:
                val = _clean_val(f.get("phone") or f.get("email"))
                f["value"] = val
            else:
                sval = str(val)
                if "@" in sval and not f.get("email"):
                    f["email"] = sval
                if any(c.isdigit() for c in sval) and not f.get("phone"):
                    f["phone"] = sval
        elif field == "country_of_origin":
            if val is None:
                val = _clean_val(f.get("country"))
                f["value"] = val
            elif not f.get("country"):
                f["country"] = str(val)
        elif field == "generic_name":
            if val is None:
                val = _clean_val(f.get("name"))
                f["value"] = val
            elif not f.get("name"):
                f["name"] = str(val)
        elif field == "fssai_license":
            if val is None:
                val = _clean_val(f.get("license_number"))
                f["value"] = val
            elif not f.get("license_number"):
                f["license_number"] = str(val)
        elif field == "batch_number":
            if val is None:
                val = _clean_val(f.get("batch_number"))
                f["value"] = val
            elif not f.get("batch_number"):
                f["batch_number"] = str(val)
        elif field == "dimensions":
            if val is None:
                val = _clean_val(f.get("size_str"))
                f["value"] = val
            elif not f.get("size_str"):
                f["size_str"] = str(val)

        # 2. Synchronize visible_text and raw_text
        if not f.get("raw_text") and f.get("visible_text"):
            f["raw_text"] = f["visible_text"]
        elif not f.get("visible_text") and f.get("raw_text"):
            f["visible_text"] = f["raw_text"]
        elif not f.get("raw_text") and not f.get("visible_text") and val is not None:
            f["raw_text"] = str(val)
            f["visible_text"] = str(val)

        # 3. STRICT CENTRAL INVARIANT: VERIFIED/detected requires usable value
        has_usable_value = val is not None and str(val).strip() not in ("", "None", "null", "N/A")

        if not has_usable_value:
            if f.get("status") == "VERIFIED" or f.get("detected"):
                f["status"] = "INCONCLUSIVE"
                f["detected"] = False
                f["value"] = None
                if not f.get("evidence_reason"):
                    f["evidence_reason"] = f"Declaration not detected with verifiable value on package label."
        else:
            if f.get("status") == "VERIFIED":
                f["detected"] = True

        # 4. Provenance defaults
        if not f.get("source"):
            f["source"] = "ocr"
        if "conflict" not in f:
            f["conflict"] = False
        if "confidence" not in f:
            f["confidence"] = 0.85 if f.get("status") == "VERIFIED" else 0.0

        normalized[field] = f

    return normalized
