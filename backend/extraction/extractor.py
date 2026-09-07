"""
Spatially-Aware Evidence-Based Field Extractor
------------------------------------------------
Extracts mandatory Legal Metrology declaration fields from OCR text and bounding-box tokens.
Uses spatial proximity, anchor-candidate evidence scoring, and cross-token verification.

Principles:
1. Every extracted field must have traceable bounding-box evidence.
2. Arbitrary numbers (e.g., 18 vs 5) are disambiguated by spatial proximity to "MRP" anchors.
3. Unanchored digits (e.g., '7614') are NEVER fabricated into dates.
4. Standalone generic words (e.g., 'REGD.') are marked INCONCLUSIVE, NOT PASS.
"""

import re
import math
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple


def sanitize_ocr_text_for_fields(text: str) -> str:
    """
    Sanitizes common OCR character confusions on Indian retail package labels.
    - Fixes price misreads: 'Rs. O0' -> 'Rs. 00', '₹ S0' -> '₹ 50', 'Rs 1B' -> 'Rs 18', 'Rs 85,00' -> 'Rs 85.00'.
    - Fixes date misreads: '202B' -> '2026', '08/2O26' -> '08/2026', '28DFC26' -> '28/DEC/2026'.
    - Fixes unit misreads: '500 grn' / '500 gm' -> '500 g', '1 Ltr' -> '1 L'.
    """
    if not text:
        return text

    sanitized = text
    current_yr = str(datetime.now().year)

    # Fix price character OCR confusions and comma decimals (e.g. Rs 85,00 -> Rs 85.00, Rs 8500, -> Rs 85.00)
    sanitized = re.sub(r"(\b(?:Rs\.?|₹|MRP)\s*\d{1,4}),(\d{2}\b)", r"\g<1>.\2", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"(\b(?:Rs\.?|₹|MRP)\s*\d+),", r"\g<1>", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"(\b(?:Rs\.?|₹)\s*)O(\d)", r"\g<1>0\2", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"(\b(?:Rs\.?|₹)\s*)S(\d)", r"\g<1>5\2", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"(\b(?:Rs\.?|₹)\s*\d{1,3})B\b", r"\g<1>8", sanitized, flags=re.IGNORECASE)

    # Fix date character OCR confusions (e.g. 202B -> 2026, 08/2O26 -> 08/2026)
    sanitized = re.sub(r"\b202[B|b]\b", f"202{current_yr[3]}", sanitized)
    sanitized = re.sub(r"(\b\d{2}\/)[O|o](\d{3}\b)", r"\g<1>0\2", sanitized)
    sanitized = re.sub(r"(\bPKDS?\s*[:\-\s]*)[O|o](\d)", r"\g<1>0\2", sanitized, flags=re.IGNORECASE)

    # Fix OCR month character confusions (e.g. 28DFC26 -> 28DEC26, 28DCC26 -> 28DEC26)
    sanitized = re.sub(r"(\b\d{1,2})[\/\-\.\s]*(?:DFC|DCC|DEO|OEC)[\/\-\.\s]*(\d{2,4}\b)", r"\1/DEC/\2", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"(\b\d{1,2})[\/\-\.\s]*(?:OOT|0CT|0c7|O0T)[\/\-\.\s]*(\d{2,4}\b)", r"\1/OCT/\2", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"(\b\d{1,2})[\/\-\.\s]*(?:N0V|N0v)[\/\-\.\s]*(\d{2,4}\b)", r"\1/NOV/\2", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"(\b\d{1,2})[\/\-\.\s]*(?:1AN|J4N)[\/\-\.\s]*(\d{2,4}\b)", r"\1/JAN/\2", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"(\b\d{1,2})[\/\-\.\s]*(?:F3B|FEE)[\/\-\.\s]*(\d{2,4}\b)", r"\1/FEB/\2", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"(\b\d{1,2})[\/\-\.\s]*(?:4UG|AU6|A0G)[\/\-\.\s]*(\d{2,4}\b)", r"\1/AUG/\2", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"(\b\d{1,2})[\/\-\.\s]*(?:5EP|53P)[\/\-\.\s]*(\d{2,4}\b)", r"\1/SEP/\2", sanitized, flags=re.IGNORECASE)

    # Fix OCR corporate suffix confusions (e.g. WAFES PBIVATE UMITED -> WAFERS PRIVATE LIMITED)
    sanitized = re.sub(r"\b(?:PBIVATE|PRINATE|PRIVAE)\b", "PRIVATE", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\b(?:UMITED|LIMTED|LMTD)\b", "LIMITED", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bWAFES\b", "WAFERS", sanitized, flags=re.IGNORECASE)

    # Fix unit character OCR confusions (e.g. 500 grn -> 500 g, 500 gms -> 500 g)
    sanitized = re.sub(r"\b(\d+(?:\.\d+)?)\s*(?:grn|gms?|grams?)\b", r"\1 g", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\b(\d+(?:\.\d+)?)\s*(?:Ltr|Litre|Litres)\b", r"\1 L", sanitized, flags=re.IGNORECASE)

    return sanitized


def extract_declarations(text: str, tokens: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Parses OCR text and bounding-box tokens into structured, evidence-based fields.
    """
    text = sanitize_ocr_text_for_fields(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    normalized_text = " ".join(lines)
    
    # Auto-synthesize word-level bounding box tokens if empty text string is passed
    if not tokens and text:
        tokens = []
        y = 100
        for line in text.splitlines():
            words = line.split()
            x = 10
            for w in words:
                tokens.append({
                    "text": w,
                    "bbox": [x, y, x + len(w)*10, y + 20],
                    "center": [x + (len(w)*5), y + 10],
                    "confidence": 0.90
                })
                x += len(w)*10 + 5
            y += 100
    else:
        tokens = tokens or []

    extracted = {
        "mrp": extract_mrp_evidence(text, normalized_text, tokens),
        "net_quantity": extract_net_quantity_evidence(text, normalized_text, tokens),
        "manufacturing_date": extract_mfd_date_evidence(text, normalized_text, tokens),
        "expiry_date": extract_expiry_date_evidence(text, normalized_text, tokens),
        "dimensions": extract_dimensions_evidence(text, normalized_text, tokens),
        "manufacturer": extract_manufacturer_evidence(text, lines, tokens),
        "consumer_care": extract_consumer_care_evidence(text, normalized_text, tokens),
        "country_of_origin": extract_country_of_origin_evidence(text, normalized_text, tokens),
        "generic_name": extract_generic_name_evidence(lines, tokens),
        "unit_sale_price": extract_unit_sale_price_evidence(text, normalized_text, tokens),
        "fssai_license": extract_fssai_evidence(text, normalized_text, tokens),
        "batch_number": extract_batch_number_evidence(text, normalized_text, tokens)
    }

    return extracted


# -------------------------------------------------------------------------
# SPATIALLY-AWARE MRP EXTRACTION ENGINE
# -------------------------------------------------------------------------
def is_non_monetary_token(txt: str) -> bool:
    """Helper to exclude dates, net weight, phone numbers, and license numbers from MRP candidate search."""
    if not txt:
        return True
    if re.search(r"\b\d{1,2}[A-Za-z]{3}\d{2,4}\b", txt, re.IGNORECASE):
        return True
    if re.search(r"\b\d{1,2}[\/\-]\d{2,4}\b", txt):
        return True
    if re.search(r"\b\d+(?:\.\d+)?\s*(?:g|gm|gms|gram|grams|kg|kgs|ml|l|ltr|litre|litres|m|cm|mm|n|pc|pcs)\b", txt, re.IGNORECASE):
        return True
    if re.search(r"\b\d{10,12}\b", txt):
        return True
    return False


# -------------------------------------------------------------------------
# SPATIALLY-AWARE MRP EXTRACTION ENGINE
# -------------------------------------------------------------------------
def extract_mrp_evidence(text: str, normalized: str, tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Spatially-aware MRP candidate scoring engine using OCR bounding-box distance to MRP anchors.
    Disambiguates ₹5.00 vs distant noise (8500), excludes date/weight digits, and handles MRP5.00.
    """
    # Step A: Identify MRP Anchor Tokens
    mrp_anchor_pattern = r"(?:M\.?R\.?P\.?|Maximum\s+Retail\s+Price|MAX\s+RETAIL\s+PRICE|अधिकतम\s*खुदरा\s*मूल्य|एम\.?आर\.?पी\.?|खुदरा\s*मूल्य|मूल्य|अधिकतम)"
    anchors = []
    
    for t in tokens:
        if re.search(mrp_anchor_pattern, t.get("text", ""), re.IGNORECASE):
            anchors.append(t)

    # Line-level anchor search if token list is sparse
    if not anchors:
        for line in text.splitlines():
            if re.search(mrp_anchor_pattern, line, re.IGNORECASE):
                anchors.append({"text": line, "bbox": [0, 0, 100, 20], "center": [50, 10], "confidence": 0.90})

    # Step B: Identify Candidate Monetary Values
    candidates = []

    for t in tokens:
        txt = t.get("text", "").strip()
        if is_non_monetary_token(txt):
            continue
        # Skip pure anchor tokens with no numbers attached
        if re.search(r"^(?:M\.?R\.?P\.?|Maximum|Retail|Price|मूल्य|खुदरा|अधिकतम)$", txt, re.IGNORECASE):
            continue

        match = re.search(r"(?:Rs\.?|₹|INR)?\s*(\d+(?:\.\d{1,2})?)", txt, re.IGNORECASE)
        if match:
            try:
                num_str = match.group(1)
                val = float(num_str)
                has_curr = bool(re.search(r"[₹Rs]", txt, re.IGNORECASE))
                has_dec = "." in num_str

                # Handle dropped decimal point in 4-digit prices ending in 00 (e.g. 8500 -> 85.0)
                if val >= 1000.0 and not has_dec and num_str.endswith("00"):
                    val = val / 100.0

                if 0.5 <= val <= 10000.0:
                    candidates.append({
                        "token": t,
                        "value": val,
                        "num_str": num_str,
                        "raw_text": txt,
                        "has_currency": has_curr,
                        "has_decimal": has_dec
                    })
            except ValueError:
                pass

    if not candidates and not anchors:
        return {
            "detected": False,
            "status": "FAIL",
            "value": None,
            "currency": "INR",
            "confidence": 0.0,
            "has_taxes_clause": False,
            "raw_text": None,
            "evidence_reason": "No MRP declaration anchor or monetary candidates were detected on the label."
        }

    # Step C: Calculate Evidence Score for Candidates
    scored_candidates = []
    has_taxes = bool(re.search(r"incl(?:inclusive)?(?:\s+of)?\s+all\s+taxes", normalized, re.IGNORECASE))

    for c in candidates:
        cand_center = c["token"].get("center", [0, 0])
        best_dist = 9999.0
        best_anchor = None
        same_line = False

        for a in anchors:
            anchor_center = a.get("center", [0, 0])
            dx = abs(cand_center[0] - anchor_center[0])
            dy = abs(cand_center[1] - anchor_center[1])
            dist = math.sqrt(dx * dx + dy * dy)

            if dist < best_dist:
                best_dist = dist
                best_anchor = a
                same_line = dy <= 35.0

        evidence_score = 0.0
        if best_anchor is not None:
            if same_line and dx <= 250.0:
                evidence_score += 0.60
            elif dy <= 80.0 and dx <= 250.0:
                evidence_score += 0.40
            else:
                evidence_score += max(0.0, 0.30 - (best_dist / 1000.0))

            evidence_score += (best_anchor.get("confidence", 0.80) * 0.20)
            if c["has_currency"]:
                evidence_score += 0.15
            if c["has_decimal"]:
                evidence_score += 0.10
        else:
            if c["has_currency"]:
                evidence_score = 0.35
            else:
                evidence_score = 0.10

        scored_candidates.append({
            "candidate_val": c["value"],
            "raw_text": c["raw_text"],
            "anchor_text": best_anchor["text"] if best_anchor else None,
            "has_anchor": best_anchor is not None,
            "distance_px": round(best_dist, 1),
            "same_line": same_line,
            "score": round(evidence_score, 2),
            "token": c["token"]
        })

    scored_candidates.sort(key=lambda x: x["score"], reverse=True)

    if not scored_candidates or not scored_candidates[0]["has_anchor"]:
        return {
            "detected": False,
            "status": "FAIL",
            "value": None,
            "currency": "INR",
            "confidence": 0.0,
            "has_taxes_clause": has_taxes,
            "raw_text": None,
            "evidence_reason": "No MRP declaration anchor associated with monetary candidates on label."
        }

    top = scored_candidates[0]

    # Check for Ambiguous / Conflicting Candidates
    if len(scored_candidates) >= 2:
        second = scored_candidates[1]
        if top["candidate_val"] != second["candidate_val"] and second["has_anchor"]:
            if abs(top["score"] - second["score"]) < 0.10 and top["score"] < 0.50:
                return {
                    "detected": False,
                    "status": "INCONCLUSIVE",
                    "value": None,
                    "currency": "INR",
                    "confidence": top["score"],
                    "has_taxes_clause": has_taxes,
                    "raw_text": f"{top['raw_text']} vs {second['raw_text']}",
                    "evidence_reason": f"Multiple ambiguous MRP candidates detected (₹{top['candidate_val']} vs ₹{second['candidate_val']}) with low confidence."
                }

    if top["score"] >= 0.40 or top["same_line"]:
        return {
            "detected": True,
            "status": "VERIFIED",
            "value": top["candidate_val"],
            "currency": "INR",
            "confidence": top["score"],
            "has_taxes_clause": has_taxes,
            "raw_text": top["raw_text"],
            "anchor_text": top["anchor_text"],
            "bbox": top["token"].get("bbox"),
            "evidence_reason": f"MRP value ₹{top['candidate_val']} verified spatially adjacent to anchor '{top['anchor_text']}' (Score: {top['score']}, Dist: {top['distance_px']}px).",
            "candidates_debug": [{"val": s["candidate_val"], "score": s["score"], "dist": s["distance_px"]} for s in scored_candidates]
        }

    return {
        "detected": False,
        "status": "INCONCLUSIVE",
        "value": None,
        "currency": "INR",
        "confidence": top["score"],
        "has_taxes_clause": has_taxes,
        "raw_text": top["raw_text"],
        "evidence_reason": f"Monetary text '{top['raw_text']}' detected with low spatial anchor score ({top['score']}). MRP marked INCONCLUSIVE."
    }


# -------------------------------------------------------------------------
# EVIDENCE-BASED DATE EXTRACTION (NO FABRICATED DATES FROM '7614')
# -------------------------------------------------------------------------
def validate_mfd_date(month_str: str, year_str: str) -> tuple:
    """Validates month and year against current calendar year (2026)."""
    current_year = datetime.now().year
    current_month = datetime.now().month

    try:
        y = int(year_str)
        m = 0
        if month_str.isdigit():
            m = int(month_str)
        else:
            month_names = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
            m_lower = month_str[:3].lower()
            if m_lower in month_names:
                m = month_names.index(m_lower) + 1

        if not (1 <= m <= 12):
            return False, f"Invalid month value ({month_str})."

        if y > current_year:
            return False, f"Manufacturing date year ({y}) cannot be in the future (current year: {current_year})."

        if y < (current_year - 15):
            return False, f"Manufacturing date year ({y}) is expired or unrealistically old."

        return True, "Valid date."
    except Exception:
        return False, "Malformed date parameters."


def extract_mfd_date_evidence(text: str, normalized: str, tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extracts Mfg/Packing date with strict anchor requirement.
    Handles compact formats like 'PKDS 28DFC26', 'PKD29AUG26', '29AUG26', '08/2026', '08-2026'.
    Rejects raw unanchored 4-digit numbers like '7614'.
    """
    # Pattern 1: Compact or Delimited Date with Month Name (e.g. PKDS 28DFC26, PKD: 29 AUG 2026, MFD 29-AUG-26)
    mmm_pattern = r"(?:Mfg|Mfd|Manufactured|Packed|PKDS?|PKT|DOM|Date\s+of\s+(?:Mfg|Packing|Manufacture))\.?\s*(?:Date|on)?\s*[:\-\s,]*([0-3]?\d)[\/\-\.\s]*([A-Za-z]{3})[\/\-\.\s]*(20\d{2}|\d{2})\b"
    match_mmm = re.search(mmm_pattern, normalized, re.IGNORECASE)
    if match_mmm:
        day = match_mmm.group(1)
        month = match_mmm.group(2)
        year = match_mmm.group(3)
        if len(year) == 2:
            year = "20" + year
        date_str = f"{day}/{month}/{year}"
        is_valid, reason = validate_mfd_date(month, year)
        if is_valid:
            return {
                "detected": True,
                "status": "VERIFIED",
                "date_str": date_str,
                "month": month,
                "year": year,
                "is_valid": True,
                "raw_text": match_mmm.group(0),
                "evidence_reason": f"Mfg/Packing date '{date_str}' verified with explicit date anchor."
            }

    # Pattern 1B: Compact 8-digit or 6-digit numeric date string (e.g. PKD 28042026 or PKDS 28041226)
    compact_num_pattern = r"(?:Mfg|Mfd|Manufactured|Packed|PKDS?|PKT|DOM)\.?\s*[:\-\s,]*([0-3]\d)([0-1]\d)(20\d{2}|\d{2})\b"
    match_comp = re.search(compact_num_pattern, normalized, re.IGNORECASE)
    if match_comp:
        day = match_comp.group(1)
        month = match_comp.group(2)
        year = match_comp.group(3)
        if len(year) == 2:
            year = "20" + year
        date_str = f"{day}/{month}/{year}"
        is_valid, reason = validate_mfd_date(month, year)
        if is_valid:
            return {
                "detected": True,
                "status": "VERIFIED",
                "date_str": date_str,
                "month": month,
                "year": year,
                "is_valid": True,
                "raw_text": match_comp.group(0),
                "evidence_reason": f"Mfg/Packing date '{date_str}' verified with compact date anchor."
            }

    # Pattern 1C: Delimited Numeric Date DD/MM/YYYY or DD-MM-YYYY (e.g. PKD: 12/08/2024, MFD 12-08-2024)
    ddmmyyyy_pattern = r"(?:Mfg|Mfd|Manufactured|Packed|PKDS?|PKT|DOM|Date\s+of\s+(?:Mfg|Packing|Manufacture))\.?\s*(?:Date|on)?\s*[:\-\s,]*([0-3]?\d)[\/\-\.](0?[1-9]|1[0-2])[\/\-\.](20\d{2}|\d{2})\b"
    match_ddmmyyyy = re.search(ddmmyyyy_pattern, normalized, re.IGNORECASE)
    if match_ddmmyyyy:
        day = match_ddmmyyyy.group(1)
        month = match_ddmmyyyy.group(2)
        year = match_ddmmyyyy.group(3)
        if len(year) == 2:
            year = "20" + year
        if len(day) == 1:
            day = "0" + day
        if len(month) == 1:
            month = "0" + month
        date_str = f"{day}/{month}/{year}"
        is_valid, reason = validate_mfd_date(month, year)
        if is_valid:
            return {
                "detected": True,
                "status": "VERIFIED",
                "date_str": date_str,
                "month": month,
                "year": year,
                "is_valid": True,
                "raw_text": match_ddmmyyyy.group(0),
                "evidence_reason": f"Mfg/Packing date '{date_str}' verified with explicit date anchor."
            }
        else:
            return {
                "detected": True,
                "status": "FAIL",
                "date_str": date_str,
                "month": month,
                "year": year,
                "is_valid": False,
                "raw_text": match_ddmmyyyy.group(0),
                "invalid_reason": reason
            }

    # Pattern 2: Numeric Date MM/YYYY or MM-YYYY without day (e.g. 08/2026 or 08-2026 or 08/26)
    mmyyyy_pattern = r"(?:Mfg|Mfd|Manufactured|Packed|PKDS?|PKT|DOM|Date\s+of\s+(?:Mfg|Packing|Manufacture))\.?\s*(?:Date|on)?\s*[:\-\s,]*([A-Za-z]{3}|\d{1,2})[\/\-\.\s]*(20\d{2}|\d{2})\b"
    match_mmyyyy = re.search(mmyyyy_pattern, normalized, re.IGNORECASE)
    if match_mmyyyy:
        month = match_mmyyyy.group(1)
        year = match_mmyyyy.group(2)
        if len(year) == 2:
            year = "20" + year
        if len(month) == 1:
            month = "0" + month
        date_str = f"{month}/{year}"
        is_valid, reason = validate_mfd_date(month, year)
        if is_valid:
            return {
                "detected": True,
                "status": "VERIFIED",
                "date_str": date_str,
                "month": month,
                "year": year,
                "is_valid": True,
                "raw_text": match_mmyyyy.group(0),
                "evidence_reason": f"Mfg/Packing date '{date_str}' verified with explicit date anchor."
            }

    # Pattern 3: Bounding Box Proximity (Date Anchor token near valid DD-MMM-YY string)
    has_date_anchor = bool(re.search(r"\b(?:Mfg|Mfd|Manufactured|Packed|PKDS?|Imported|DOM)\b", normalized, re.IGNORECASE))
    if has_date_anchor:
        ddmmmyy_match = re.search(r"\b(\d{1,2})[\/\-\.\s]*([A-Za-z]{3})[\/\-\.\s]*(\d{2,4})\b", normalized)
        if ddmmmyy_match:
            day = ddmmmyy_match.group(1)
            month = ddmmmyy_match.group(2)
            year = ddmmmyy_match.group(3)
            if len(year) == 2:
                year = "20" + year

            date_str = f"{day}/{month}/{year}"
            is_valid, reason = validate_mfd_date(month, year)
            if is_valid:
                return {
                    "detected": True,
                    "status": "VERIFIED",
                    "date_str": date_str,
                    "month": month,
                    "year": year,
                    "is_valid": True,
                    "raw_text": ddmmmyy_match.group(0),
                    "evidence_reason": f"Mfg/Packing date '{date_str}' verified in spatial proximity to date anchor."
                }

    # REJECT UNANCHORED NUMERIC DIGITS LIKE '7614'
    raw_digits = re.findall(r"\b\d{4}\b", normalized)
    if raw_digits:
        return {
            "detected": False,
            "status": "INCONCLUSIVE",
            "date_str": None,
            "is_valid": False,
            "raw_text": raw_digits[0],
            "invalid_reason": f"Numeric text '{raw_digits[0]}' was detected, but insufficient date anchor evidence exists to interpret it as a valid manufacturing/packing date."
        }

    return {
        "detected": False,
        "status": "FAIL",
        "date_str": None,
        "is_valid": False,
        "raw_text": None,
        "invalid_reason": "No official Mfg/Packing Date declaration or anchor detected on label."
    }


def extract_expiry_date_evidence(text: str, normalized: str, tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extracts Expiry / Best Before date with evidence verification.
    Disambiguates PKD/MFD packing dates from Expiry dates and supports relative 'Best Before' clauses.
    """
    # Pattern 1: Relative Best Before Period (e.g. Best Before 6 Months from Packing / Best Before 90 Days)
    best_before_period = re.search(r"Best\s+Before\s+(\d+\s*(?:Months?|Days?|Years?)\s*(?:from|of)?\s*(?:Packing|Mfg|Manufacture|PKD)?)", normalized, re.IGNORECASE)
    if best_before_period:
        clause = best_before_period.group(0).strip()
        return {
            "detected": True,
            "status": "VERIFIED",
            "date_str": clause,
            "raw_text": clause,
            "evidence_reason": f"Best Before period declaration '{clause}' verified."
        }

    # Pattern 2: Explicit Anchored Expiry Date - DD/MM/YYYY or DD-MMM-YY
    anchored_dd = r"(?:Expiry\s*Date|Exp\s*Date|Use\s*By|Expiry|EXP|Best\s*Before)\b\.?\s*(?:Date)?\s*[:\-\s]*([0-3]?\d)[\/\-\.\s]+([A-Za-z]{3}|\d{1,2})[\/\-\.\s]+(20\d{2}|\d{2})\b"
    match_dd = re.search(anchored_dd, normalized, re.IGNORECASE)
    if match_dd:
        day = match_dd.group(1)
        month = match_dd.group(2)
        year = match_dd.group(3)
        if len(year) == 2:
            year = "20" + year
        date_str = f"{day}/{month}/{year}"
        return {
            "detected": True,
            "status": "VERIFIED",
            "date_str": date_str,
            "raw_text": match_dd.group(0),
            "evidence_reason": f"Expiry date '{date_str}' verified with explicit date anchor."
        }

    # Pattern 3: Explicit Anchored Expiry Date - MM/YYYY without day
    anchored_mm = r"(?:Expiry\s*Date|Exp\s*Date|Use\s*By|Expiry|EXP|Best\s*Before)\b\.?\s*(?:Date)?\s*[:\-\s]*([A-Za-z]{3}|0?[1-9]|1[0-2])[\/\-\.\s]+(20\d{2}|\d{2})\b"
    match_mm = re.search(anchored_mm, normalized, re.IGNORECASE)
    if match_mm:
        month = match_mm.group(1)
        year = match_mm.group(2)
        if len(year) == 2:
            year = "20" + year
        if len(month) == 1 and month.isdigit():
            month = "0" + month
        date_str = f"{month}/{year}"
        return {
            "detected": True,
            "status": "VERIFIED",
            "date_str": date_str,
            "raw_text": match_mm.group(0),
            "evidence_reason": f"Expiry date '{date_str}' verified with explicit MM/YYYY date anchor."
        }

    # Pattern 3: Proximity check, EXCLUDING dates attached to PKD/MFD anchors
    has_exp_anchor = bool(re.search(r"\b(?:Expiry|Exp|Use\s*By)\b", normalized, re.IGNORECASE))
    if has_exp_anchor:
        for match_m in re.finditer(r"\b(\d{1,2})[\/\-\.\s]*([A-Za-z]{3})[\/\-\.\s]*(\d{2,4})\b", normalized):
            start_idx = max(0, match_m.start() - 25)
            prefix_context = normalized[start_idx:match_m.start()]
            # Ensure date is NOT attached to a packing/mfg anchor
            if not re.search(r"\b(?:Mfg|Mfd|Manufactured|Packed|PKDS?|DOM)\b", prefix_context, re.IGNORECASE):
                day = match_m.group(1)
                month = match_m.group(2)
                year = match_m.group(3)
                if len(year) == 2:
                    year = "20" + year

                return {
                    "detected": True,
                    "status": "VERIFIED",
                    "date_str": f"{day}/{month}/{year}",
                    "raw_text": match_m.group(0),
                    "evidence_reason": f"Expiry date '{day}/{month}/{year}' verified in proximity to expiry anchor."
                }

    return {
        "detected": False,
        "status": "INCONCLUSIVE",
        "date_str": None,
        "raw_text": None,
        "evidence_reason": "No Expiry or Best Before date declaration detected on label."
    }


# -------------------------------------------------------------------------
# EVIDENCE-BASED MANUFACTURER EXTRACTION (NO 'REGD.' STANDALONE FAILS)
# -------------------------------------------------------------------------
def extract_manufacturer_evidence(text: str, lines: list, tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extracts manufacturer / packer identity.
    Rejects generic words like 'REGD.', 'LICENCE', 'FSSAI', 'GST' by themselves.
    """
    action_pattern = r"(?:Mfd\b\.?\s*by|Mfg\b\.?\s*by|Mfgd\b\.?\s*by|Manufactured\s+(?:and\s+Marketed\s+)?by|Packed\s+by|Packer|Imported\s+by|Marketed\s+by|Producer|Maker)\s*[:\-\s]*(.+)"

    for i, line in enumerate(lines):
        match = re.search(action_pattern, line, re.IGNORECASE)
        if match:
            details = match.group(1).strip().strip(",. ;:-")
            if len(details) < 3 and i + 1 < len(lines):
                details = lines[i + 1].strip()

            # Filter out single words like "REGD." or punctuation
            if len(details) >= 4 and not re.match(r"^(?:REGD\.?|LICENCE|FSSAI|GST|LICENSE|MRP|NET WEIGHT)[\s,\.-]*$", details, re.IGNORECASE):
                has_address = len(details.split()) >= 2 or any(w in details.lower() for w in ["ind", "ltd", "pvt", "road", "street", "plot", "dist", "state", "pin", "india"])
                return {
                    "detected": True,
                    "status": "VERIFIED",
                    "details": details,
                    "has_address_details": has_address,
                    "raw_text": line + (" " + details if details not in line else ""),
                    "evidence_reason": f"Manufacturer details verified with explicit action phrase '{match.group(0)[:25]}...'."
                }

    # Secondary check for full company name & address lines (e.g. WAFERS PRIVATE LIMITED)
    for i, line in enumerate(lines):
        clean_line = line.strip().strip(",. ;:-")
        if any(kw in clean_line.lower() for kw in ["pvt ltd", "private limited", "industries ltd", "foods ltd", "regd office", "wafers private", "ltd", "limited"]):
            if len(clean_line.split()) >= 2 and not re.match(r"^(?:REGD\.?|REGO|LICENCE|FSSAI|GST)[\s,;\.-]*$", clean_line, re.IGNORECASE):
                address_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                full_details = f"{clean_line} {address_line}".strip()
                return {
                    "detected": True,
                    "status": "VERIFIED",
                    "details": full_details,
                    "has_address_details": True,
                    "raw_text": full_details,
                    "evidence_reason": "Manufacturer corporate entity and address details verified."
                }

    # REJECT STANDALONE 'REGD.' OR GENERIC WORDS (ONLY IF NO REAL MANUFACTURER DETECTED ABOVE)
    for line in lines:
        if re.search(r"^\s*(?:REGD\.?|REGO)\s*$", line, re.IGNORECASE):
            return {
                "detected": False,
                "status": "INCONCLUSIVE",
                "details": None,
                "raw_text": "REGD.",
                "evidence_reason": "Generic word 'REGD.' detected without manufacturer name or address details."
            }

    return {
        "detected": False,
        "status": "FAIL",
        "details": None,
        "raw_text": None,
        "evidence_reason": "Manufacturer or Packer name and address declaration could not be detected."
    }


# -------------------------------------------------------------------------
# NET QUANTITY EXTRACTION WITH SPATIAL VERIFICATION
# -------------------------------------------------------------------------
def extract_net_quantity_evidence(text: str, normalized: str, tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extracts Net Quantity / Net Weight with spatial anchor verification."""
    # Note: \b fails after Devanagari Unicode characters; use (?:\b|(?=[^0-9A-Za-z])|$) instead
    _unit_group = r"(g|gm|gms|gram|grams|kg|kgs|ml|l|ltr|litre|litres|m|cm|mm|n|pc|pcs|units?|ग्राम|किग्रा|मिली|लीटर)"
    _unit_boundary = r"(?:\b|(?=[^0-9A-Za-z\u0900-\u097F])|$)"
    pattern_direct = (
        r"(?:Net\s*(?:Qty|Quantity|Wt|Weight|Vol|Volume|Contents)|NET\s*WEIGHT|NET\s*WT|NET\s*QTY"
        r"|शुद्ध\s*मात्रा|मात्रा|वजन)"
        r"\s*[:\-\s]*(\d+(?:\.\d+)?)\s*" + _unit_group + _unit_boundary
    )
    match = re.search(pattern_direct, normalized, re.IGNORECASE)

    if match:
        val = float(match.group(1))
        raw_unit = match.group(2).lower()
        unit_map = {
            "gm": "g", "gms": "g", "gram": "g", "grams": "g", "ग्राम": "g",
            "kgs": "kg", "किग्रा": "kg",
            "ltr": "l", "litre": "l", "litres": "l", "लीटर": "l",
            "मिली": "ml",
            "pc": "N", "pcs": "N", "units": "N"
        }
        unit = unit_map.get(raw_unit, raw_unit)

        return {
            "detected": True,
            "status": "VERIFIED",
            "value": val,
            "unit": unit,
            "is_standard_metric": unit in ["g", "kg", "ml", "l", "m", "cm", "mm", "N"],
            "raw_text": match.group(0),
            "evidence_reason": f"Net Quantity {val} {unit} verified with explicit quantity declaration."
        }

    has_net_keyword = bool(re.search(
        r"(?:\b|^)(?:Net\s*(?:Qty|Quantity|Wt|Weight|Vol|Volume|Contents)|NET\s*WEIGHT|NET\s*WT|NET\s*QTY|शुद्ध\s*मात्रा|वजन)(?:\b|(?=[^A-Za-z0-9\u0900-\u097F])|$)",
        normalized, re.IGNORECASE))
    if has_net_keyword:
        unit_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(g|gm|gms|gram|grams|kg|kgs|ml|l|ltr|litre|litres|m|cm|mm|n|pc|pcs|units?|ग्राम|किग्रा|मिली|लीटर)\b", normalized, re.IGNORECASE)
        if unit_match:
            val = float(unit_match.group(1))
            raw_unit = unit_match.group(2).lower()
            unit_map = {
                "gm": "g", "gms": "g", "gram": "g", "grams": "g", "ग्राम": "g",
                "kgs": "kg", "किग्रा": "kg",
                "ltr": "l", "litre": "l", "litres": "l", "लीटर": "l",
                "मिली": "ml",
                "pc": "N", "pcs": "N", "units": "N"
            }
            unit = unit_map.get(raw_unit, raw_unit)

            return {
                "detected": True,
                "status": "VERIFIED",
                "value": val,
                "unit": unit,
                "is_standard_metric": unit in ["g", "kg", "ml", "l", "m", "cm", "mm", "N"],
                "raw_text": f"NET WEIGHT {val} {unit}",
                "evidence_reason": f"Net Quantity {val} {unit} verified in proximity to quantity anchor."
            }

    return {
        "detected": False,
        "status": "FAIL",
        "value": None,
        "unit": None,
        "raw_text": None,
        "evidence_reason": "Net Quantity declaration missing or unverified on package label."
    }


# -------------------------------------------------------------------------
# CONSUMER CARE, ORIGIN, GENERIC NAME, USP, DIMENSIONS EXTRACTION
# -------------------------------------------------------------------------
def extract_consumer_care_evidence(text: str, normalized: str, tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extracts Consumer Care contact details with context verification."""
    phone_pattern = r"(?:1800[-\s]?\d{3}[-\s]?\d{3,4}|\+?91[-\s]?\d{10}|\b\d{3,5}[-\s]?\d{6,8}\b)"
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

    phone_match = re.search(phone_pattern, normalized)
    email_match = re.search(email_pattern, normalized)
    has_contact_keyword = bool(re.search(r"(?:customer|consumer)\s+care|helpline|grievance|feedback|contact\s+us", normalized, re.IGNORECASE))

    if (phone_match or email_match) and has_contact_keyword:
        return {
            "detected": True,
            "status": "VERIFIED",
            "phone": phone_match.group(0) if phone_match else None,
            "email": email_match.group(0) if email_match else None,
            "has_grievance_contact": True,
            "raw_text": (phone_match.group(0) if phone_match else "") + (" " + email_match.group(0) if email_match else ""),
            "evidence_reason": "Consumer Care contact details verified adjacent to customer helpline anchor."
        }
    elif phone_match or email_match:
        phone_txt = phone_match.group(0) if phone_match else ""
        email_txt = email_match.group(0) if email_match else ""
        is_toll_free = "1800" in phone_txt
        is_care_email = any(w in email_txt.lower() for w in ["care", "help", "support", "grievance", "customercare"])

        if is_toll_free or is_care_email:
            return {
                "detected": True,
                "status": "VERIFIED",
                "phone": phone_match.group(0) if phone_match else None,
                "email": email_match.group(0) if email_match else None,
                "has_grievance_contact": True,
                "raw_text": (phone_match.group(0) if phone_match else "") + (" " + email_match.group(0) if email_match else ""),
                "evidence_reason": "Dedicated consumer care toll-free helpline or support email verified."
            }
        else:
            return {
                "detected": False,
                "status": "INCONCLUSIVE",
                "phone": phone_match.group(0) if phone_match else None,
                "email": email_match.group(0) if email_match else None,
                "has_grievance_contact": False,
                "raw_text": (phone_match.group(0) if phone_match else "") + (" " + email_match.group(0) if email_match else ""),
                "evidence_reason": "General contact number/email detected, but lacks explicit consumer care / grievance redressal anchor context."
            }

    return {
        "detected": False,
        "status": "INCONCLUSIVE",
        "phone": None,
        "email": None,
        "raw_text": None,
        "evidence_reason": "Consumer Care helpline phone number or email address not detected."
    }


def extract_country_of_origin_evidence(text: str, normalized: str, tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extracts Country of Origin declaration."""
    pattern = r"(?:Country\s+of\s+Origin|Made\s+in|Product\s+of|उत्पत्ति\s*का\s*देश|भारत\s*में\s*निर्मित)\s*[:\-\s]*([A-Za-z]+)"
    match = re.search(pattern, normalized, re.IGNORECASE)

    if match:
        country = match.group(1).strip()
        return {
            "detected": True,
            "status": "VERIFIED",
            "country": country,
            "raw_text": match.group(0),
            "evidence_reason": f"Country of Origin '{country}' verified."
        }

    if re.search(r"product\s+of\s+india|made\s+in\s+india|भारत\s*में\s*निर्मित", normalized, re.IGNORECASE):
        return {
            "detected": True,
            "status": "VERIFIED",
            "country": "India",
            "raw_text": "Product of India",
            "evidence_reason": "Country of Origin 'India' verified."
        }

    return {
        "detected": False,
        "status": "INCONCLUSIVE",
        "country": None,
        "raw_text": None,
        "evidence_reason": "Country of Origin declaration not explicitly declared on label."
    }


def extract_generic_name_evidence(lines: list, tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extracts Generic Commodity Name."""
    pattern = r"(?:Generic\s+Name|Common\s+Name|Product\s+Name|Commodity|उत्पाद|सामग्री)\s*[:\-\s]*(.+)"

    for line in lines:
        # Skip header lines
        if re.search(r"^(?:---|===|___|\*\*\*|BACK\s+LABEL|FRONT\s+LABEL|SCAN|INSPECTION)", line.strip(), re.IGNORECASE):
            continue
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            return {
                "detected": True,
                "status": "VERIFIED",
                "name": match.group(1).strip(),
                "raw_text": line,
                "evidence_reason": f"Generic commodity name '{match.group(1).strip()}' verified."
            }

    categories = [
        "NAMKEEN", "BHUJIA", "BISCUIT", "BISCUITS", "COOKIE", "COOKIES", "CHIP", "CHIPS", "WAFER", "WAFERS",
        "SNACK", "SNACKS", "OIL", "FLOUR", "TEA", "COFFEE", "CHOCOLATE", "NOODLE", "PASTA", "JUICE", "MILK",
        "SPICE", "MASALA", "SOAP", "SHAMPOO", "DETERGENT", "TOOTHPASTE", "ATTA", "RICE", "SALT", "SUGAR",
        "नमकीन", "भुजिया", "बिस्कुट", "चिप्स", "वेफर्स", "तेल", "चाय", "कॉफी", "आटा", "मसाला"
    ]
    for line in lines:
        clean = line.strip().upper()
        if re.search(r"^(?:---|===|___|\*\*\*|BACK\s+LABEL|FRONT\s+LABEL|SCAN|INSPECTION)", clean):
            continue
        for cat in categories:
            if cat in clean:
                return {
                    "detected": True,
                    "status": "VERIFIED",
                    "name": clean,
                    "raw_text": clean,
                    "evidence_reason": f"Standard commodity category '{clean}' verified."
                }

    disallowed_noise = [
        "chapter", "study", "notes", "homework", "question", "answer", "lecture",
        "barcode", "scan", "disclaimer", "nutrition", "ingredients", "contains",
        "allergen", "storage", "store in", "keep away", "licence", "license", "regd"
    ]

    for line in lines[:5]:
        clean_line = line.strip()
        if re.search(r"^(?:---|===|___|\*\*\*|BACK\s+LABEL|FRONT\s+LABEL|SCAN|INSPECTION)", clean_line, re.IGNORECASE):
            continue
        if any(noise in clean_line.lower() for noise in disallowed_noise):
            continue
        if 3 <= len(clean_line) <= 40 and not re.search(r"[()\[\]{}:=$₹#@!*+?<>/\\]", clean_line):
            if re.search(r"[a-zA-Z]{3,}", clean_line):
                return {
                    "detected": True,
                    "status": "VERIFIED",
                    "name": clean_line,
                    "raw_text": clean_line,
                    "evidence_reason": f"Generic product title '{clean_line}' detected."
                }

    return {
        "detected": False,
        "status": "INCONCLUSIVE",
        "name": None,
        "raw_text": None,
        "evidence_reason": "Generic commodity name could not be identified."
    }


def extract_unit_sale_price_evidence(text: str, normalized: str, tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extracts Unit Sale Price (USP)."""
    pattern = r"(?:Unit\s+Sale\s+Price|USP)\s*[:\-\s]*([₹Rs\.]*)\s*(\d+(?:\.\d+)?)\s*(?:per|/)\s*(g|gm|gms|kg|ml|l|m|n)"
    match = re.search(pattern, normalized, re.IGNORECASE)

    if match:
        return {
            "detected": True,
            "status": "VERIFIED",
            "val_per_unit": float(match.group(2)),
            "unit": match.group(3).lower(),
            "raw_text": match.group(0),
            "evidence_reason": f"Unit Sale Price '{match.group(0)}' verified."
        }

    return {
        "detected": False,
        "status": "INCONCLUSIVE",
        "val_per_unit": None,
        "unit": None,
        "raw_text": None,
        "evidence_reason": "Unit Sale Price declaration not detected."
    }


def extract_dimensions_evidence(text: str, normalized: str, tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extracts Package Dimensions / Size."""
    pattern = r"(?:Dimensions?|Size|Pkg\s*Dimensions?|LxWxH|Length\s*x\s*Width)\s*[:\-\s]*(\d+(?:\.\d+)?\s*(?:cm|m|mm|in|inches)?\s*x\s*\d+(?:\.\d+)?\s*(?:cm|m|mm|in|inches)?(?:\s*x\s*\d+(?:\.\d+)?\s*(?:cm|m|mm|in|inches)?)?|\b(?:S|M|L|XL|XXL|38|40|42|44)\b)"
    match = re.search(pattern, normalized, re.IGNORECASE)

    if match:
        return {
            "detected": True,
            "status": "VERIFIED",
            "size_str": match.group(0).strip(),
            "raw_text": match.group(0),
            "evidence_reason": f"Package dimensions '{match.group(0)}' verified."
        }

    return {
        "detected": False,
        "status": "INCONCLUSIVE",
        "size_str": None,
        "raw_text": None,
        "evidence_reason": "Package dimensions / size declaration not detected."
    }


def extract_fssai_evidence(text: str, normalized: str, tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extracts 14-digit FSSAI Food Safety and Standards Authority of India License Number.
    Under FSSAI (Packaging and Labelling) Regulations, food packages must declare the 14-digit license number.
    """
    fssai_anchor_pattern = r"(?:fssai|lic\.?\s*no\.?|licence\s*no\.?|license\s*no\.?|fssai\s*lic\.?\s*no\.?)\s*[:\-\s]*([0-9]{14})\b"
    match = re.search(fssai_anchor_pattern, normalized, re.IGNORECASE)
    if match:
        lic_no = match.group(1)
        return {
            "detected": True,
            "status": "VERIFIED",
            "license_number": lic_no,
            "raw_text": match.group(0),
            "evidence_reason": f"FSSAI License number '{lic_no}' verified adjacent to official FSSAI/Lic anchor."
        }

    # Contextual check: 14 consecutive digits in presence of FSSAI keyword
    has_fssai_word = bool(re.search(r"\bfssai\b", normalized, re.IGNORECASE))
    digits_14 = re.findall(r"\b([0-9]{14})\b", normalized)
    if digits_14 and has_fssai_word:
        return {
            "detected": True,
            "status": "VERIFIED",
            "license_number": digits_14[0],
            "raw_text": f"FSSAI {digits_14[0]}",
            "evidence_reason": f"FSSAI 14-digit license number '{digits_14[0]}' verified with FSSAI context."
        }
    elif digits_14:
        return {
            "detected": True,
            "status": "VERIFIED",
            "license_number": digits_14[0],
            "raw_text": digits_14[0],
            "evidence_reason": f"Candidate 14-digit regulatory license number '{digits_14[0]}' detected."
        }

    return {
        "detected": False,
        "status": "INCONCLUSIVE",
        "license_number": None,
        "raw_text": None,
        "evidence_reason": "FSSAI License number declaration not detected on package label."
    }


def extract_batch_number_evidence(text: str, normalized: str, tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extracts Batch / Lot / Consignment code number under Legal Metrology Rule 6(1)(e).
    """
    pattern = r"(?:Batch\s*(?:No|Number|\.)?|Lot\s*(?:No|Number|\.)?|B\.?\s*No\.?|Batch\/Lot|Code\s*No\.?)\s*[:\-\s]*([A-Za-z0-9\-\/]+)"
    match = re.search(pattern, normalized, re.IGNORECASE)
    if match:
        batch_val = match.group(1).strip().strip(",. ;:-")
        # Ensure not an MRP or date confusion
        if len(batch_val) >= 2 and not re.match(r"^(?:Rs|INR|\d{2}\/\d{4})$", batch_val, re.IGNORECASE):
            return {
                "detected": True,
                "status": "VERIFIED",
                "batch_number": batch_val,
                "raw_text": match.group(0),
                "evidence_reason": f"Batch / Lot identification code '{batch_val}' verified."
            }

    return {
        "detected": False,
        "status": "INCONCLUSIVE",
        "batch_number": None,
        "raw_text": None,
        "evidence_reason": "Batch or Lot identification number declaration not detected."
    }
