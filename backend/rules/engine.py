"""
Deterministic Legal Metrology Rule Engine
------------------------------------------
Applies exact, non-probabilistic regulatory rules to extracted declarations.
Consumes evidence-based fields (VERIFIED, INCONCLUSIVE, POTENTIAL NON-COMPLIANCE)
and generates explainable 3-State Verdict:
1. COMPLIANT
2. POTENTIAL NON-COMPLIANCE
3. INCONCLUSIVE
"""

import json
import os
from typing import Dict, Any, List


RULES_FILE_PATH = os.path.join(os.path.dirname(__file__), "legal_rules.json")

def load_legal_rules() -> List[Dict[str, Any]]:
    """Loads configured Legal Metrology rules from JSON database."""
    if not os.path.exists(RULES_FILE_PATH):
        return []
    with open(RULES_FILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("rules", [])


def evaluate_compliance(
    extracted_data: Dict[str, Any],
    quality_assessment: Dict[str, Any],
    product_category: str = "packaged_goods",
    is_valid_product: bool = True
) -> Dict[str, Any]:
    """
    Evaluates extracted evidence-based fields against official Legal Metrology Rules.
    Returns structured results, evidence mapping, and 3-State Overall Verdict.
    """

    # Step 1: Check Image Quality Gate
    if not quality_assessment.get("is_readable", True):
        return {
            "overall_status": "INCONCLUSIVE",
            "verdict_title": "Inconclusive Inspection",
            "verdict_color": "warning",
            "reason": "Image quality is too blurry or dark to extract legally verifiable declarations.",
            "action_required": quality_assessment.get("message", "Please capture a clearer image."),
            "rules_applied_count": 0,
            "passed_rules_count": 0,
            "failed_rules_count": 0,
            "inconclusive_rules_count": 0,
            "rule_results": [],
            "extracted_evidence": extracted_data
        }

    rules = load_legal_rules()
    rule_results = []

    passed_count = 0
    failed_count = 0
    inconclusive_count = 0

    for rule in rules:
        categories = rule.get("applicable_categories", ["all"])
        if "all" not in categories and product_category not in categories:
            continue  # Skip rules not applicable to this category

        rule_id = rule["rule_id"]
        target_field = rule["target_field"]
        field_data = extracted_data.get(target_field, {})

        status = "FAIL"
        evidence_text = field_data.get("raw_text") or field_data.get("visible_text")
        if not evidence_text and field_data.get("value") is not None:
            evidence_text = str(field_data.get("value"))

        explanation = field_data.get("evidence_reason") or field_data.get("invalid_reason") or ""
        field_status = field_data.get("status")
        field_detected = bool(field_data.get("detected"))

        # Category-aware mandatory determination
        is_mandatory = rule.get("is_mandatory", False)
        if target_field == "expiry_date":
            # Under Rule 6(1)(e) Second Proviso & FSSAI Packaging Regulations,
            # Expiry / Best Before is mandatory for food commodities.
            is_mandatory = (product_category == "food")

        # Specific Field Validation Logic
        if target_field == "mrp":
            val = field_data.get("value")
            if field_status == "VERIFIED" and field_detected and val is not None:
                has_taxes = field_data.get("has_taxes_clause", True)
                status = "PASS"
                evidence_text = evidence_text or f"₹{val}"
                explanation = f"MRP verified: ₹{val}" + (" (incl. of all taxes)." if has_taxes else ".")
            elif field_status == "INCONCLUSIVE" or (field_detected and val is None):
                status = "INCONCLUSIVE"
                explanation = explanation or "MRP candidate evidence is inconclusive or missing value."
            else:
                status = "FAIL" if is_mandatory else "INCONCLUSIVE"
                explanation = explanation or "Maximum Retail Price (MRP) declaration could not be detected on the package label."

        elif target_field == "net_quantity":
            val = field_data.get("value")
            unit = field_data.get("unit")
            is_standard = field_data.get("is_standard_metric", True)

            if field_status == "VERIFIED" and field_detected and val is not None:
                if is_standard:
                    status = "PASS"
                    evidence_text = evidence_text or f"{val} {unit or ''}".strip()
                    explanation = f"Net Quantity verified: {val} {unit or ''} (Standard metric unit).".replace("  ", " ")
                else:
                    status = "FAIL"
                    explanation = f"Net Quantity found ({val} {unit or ''}), but unit is non-standard metric."
            elif field_status == "INCONCLUSIVE" or (field_detected and val is None):
                status = "INCONCLUSIVE"
                explanation = explanation or "Net Quantity declaration evidence is inconclusive."
            else:
                status = "FAIL" if is_mandatory else "INCONCLUSIVE"
                explanation = explanation or "Net Quantity declaration missing or unverified on package label."

        elif target_field == "manufacturing_date":
            date_str = field_data.get("date_str") or (str(field_data.get("value")) if field_data.get("value") is not None else None)
            is_valid = field_data.get("is_valid", True)
            invalid_reason = field_data.get("invalid_reason", "")

            if field_status == "VERIFIED" and field_detected and date_str is not None:
                if is_valid:
                    status = "PASS"
                    evidence_text = evidence_text or date_str
                    explanation = f"Month and Year of Manufacture/Packing verified: {date_str}."
                else:
                    status = "FAIL"
                    explanation = f"Invalid Manufacturing Date detected '{date_str}': {invalid_reason}"
            elif field_status == "INCONCLUSIVE" or (field_detected and date_str is None):
                status = "INCONCLUSIVE"
                explanation = explanation or "Mfg/Packing date evidence is inconclusive."
            else:
                status = "FAIL" if is_mandatory else "INCONCLUSIVE"
                explanation = explanation or "Month and Year of Manufacture or Packing declaration is missing."

        elif target_field == "manufacturer":
            details = field_data.get("details") or (str(field_data.get("value")) if field_data.get("value") is not None else None)
            if field_status == "VERIFIED" and field_detected and details is not None:
                status = "PASS"
                evidence_text = evidence_text or details
                explanation = f"Manufacturer/Packer details verified: {details}."
            elif field_status == "INCONCLUSIVE" or (field_detected and details is None):
                status = "INCONCLUSIVE"
                explanation = explanation or "Manufacturer name and address details are inconclusive."
            else:
                status = "FAIL" if is_mandatory else "INCONCLUSIVE"
                explanation = explanation or "Manufacturer or Packer name/address declaration is missing."

        elif target_field == "consumer_care":
            phone = field_data.get("phone")
            email = field_data.get("email")
            contact_val = field_data.get("value")
            has_contact = bool(phone or email or contact_val)

            if field_status == "VERIFIED" and field_detected and has_contact:
                status = "PASS"
                contact_desc = []
                if phone: contact_desc.append(f"Phone ({phone})")
                if email: contact_desc.append(f"Email ({email})")
                if not contact_desc and contact_val: contact_desc.append(f"Contact ({contact_val})")
                evidence_text = evidence_text or (phone or email or str(contact_val))
                explanation = f"Consumer Care contact verified: {', '.join(contact_desc)}."
            elif field_status == "INCONCLUSIVE" or (field_detected and not has_contact):
                status = "INCONCLUSIVE"
                explanation = explanation or "Consumer Care contact details are inconclusive."
            else:
                status = "FAIL" if is_mandatory else "INCONCLUSIVE"
                explanation = explanation or "Consumer Care contact details (phone number or email) are missing."

        elif target_field == "generic_name":
            name = field_data.get("name") or (str(field_data.get("value")) if field_data.get("value") is not None else None)
            if field_status == "VERIFIED" and field_detected and name is not None:
                status = "PASS"
                evidence_text = evidence_text or name
                explanation = f"Generic commodity name verified: '{name}'."
            elif field_status == "INCONCLUSIVE" or (field_detected and name is None):
                status = "INCONCLUSIVE"
                explanation = explanation or "Generic commodity name is inconclusive."
            else:
                status = "FAIL" if is_mandatory else "INCONCLUSIVE"
                explanation = explanation or "Generic/common commodity name is missing."

        elif target_field == "country_of_origin":
            country = field_data.get("country") or (str(field_data.get("value")) if field_data.get("value") is not None else None)
            if field_status == "VERIFIED" and field_detected and country is not None:
                status = "PASS"
                evidence_text = evidence_text or country
                explanation = f"Country of Origin explicitly verified: {country}."
            else:
                if product_category == "imported":
                    status = "FAIL"
                    explanation = "Mandatory Country of Origin declaration missing on imported package (Rule 6(1)(c))."
                else:
                    mfg_data = extracted_data.get("manufacturer", {})
                    mfg_val = mfg_data.get("details") or mfg_data.get("value")
                    mfg_verified = (mfg_data.get("status") == "VERIFIED" and bool(mfg_data.get("detected")) and mfg_val is not None)
                    if mfg_verified:
                        status = "PASS"
                        evidence_text = f"India (Implicit via: {str(mfg_val)[:40]})"
                        explanation = f"Domestic package: Implicit origin verified via Indian manufacturer address ({str(mfg_val)[:45]})."
                    else:
                        status = "INCONCLUSIVE"
                        explanation = "Country of Origin not declared and domestic manufacturer address unverified."

        elif target_field == "unit_sale_price":
            usp_val = field_data.get("value")
            if field_status == "VERIFIED" and field_detected and (usp_val is not None or (evidence_text and str(evidence_text).strip())):
                status = "PASS"
                evidence_text = evidence_text or str(usp_val)
                explanation = f"Unit Sale Price verified: {evidence_text}."
            else:
                status = "INCONCLUSIVE"
                explanation = explanation or "Unit Sale Price declaration not detected."

        elif target_field == "expiry_date":
            date_str = field_data.get("date_str") or (str(field_data.get("value")) if field_data.get("value") is not None else None)
            is_valid = field_data.get("is_valid", True)
            if field_status == "VERIFIED" and field_detected and date_str is not None:
                if is_valid:
                    status = "PASS"
                    evidence_text = evidence_text or date_str
                    explanation = f"Expiry Date / Best Before verified: {date_str}."
                else:
                    status = "FAIL"
                    explanation = f"Invalid Expiry Date detected '{date_str}'."
            else:
                if product_category == "food":
                    status = "FAIL"
                    explanation = "Mandatory Expiry Date / Best Before declaration missing on packaged food commodity (Rule 6(1)(e) Second Proviso)."
                else:
                    status = "INCONCLUSIVE"
                    explanation = explanation or "Expiry Date or Best Before declaration not detected (optional for non-perishable commodity)."

        elif target_field == "dimensions":
            size_str = field_data.get("size_str") or (str(field_data.get("value")) if field_data.get("value") is not None else None)
            if field_status == "VERIFIED" and field_detected and size_str is not None:
                status = "PASS"
                evidence_text = evidence_text or size_str
                explanation = f"Package Dimensions / Size verified: {size_str}."
            else:
                status = "INCONCLUSIVE"
                explanation = explanation or "Package Dimensions / Size declaration not detected."

        elif target_field == "fssai_license":
            lic = field_data.get("license_number") or (str(field_data.get("value")) if field_data.get("value") is not None else None)
            if field_status == "VERIFIED" and field_detected and lic is not None:
                status = "PASS"
                evidence_text = evidence_text or lic
                explanation = f"FSSAI Food Safety License verified: {lic}."
            else:
                status = "INCONCLUSIVE"
                explanation = explanation or "FSSAI Food Safety License number not detected on package label."

        elif target_field == "batch_number":
            bno = field_data.get("batch_number") or (str(field_data.get("value")) if field_data.get("value") is not None else None)
            if field_status == "VERIFIED" and field_detected and bno is not None:
                status = "PASS"
                evidence_text = evidence_text or bno
                explanation = f"Batch / Lot identification code verified: {bno}."
            else:
                status = "INCONCLUSIVE"
                explanation = explanation or "Batch or Lot identification code not detected."

        if status == "PASS":
            passed_count += 1
        elif status == "FAIL":
            failed_count += 1
        else:
            inconclusive_count += 1

        rule_results.append({
            "rule_id": rule_id,
            "rule_name": rule["rule_name"],
            "rule_clause": rule["rule_clause"],
            "target_field": target_field,
            "is_mandatory": is_mandatory,
            "status": status,
            "evidence_text": evidence_text if status == "PASS" else (evidence_text or None),
            "explanation": explanation,
            "legal_source": f"Legal Metrology (Packaged Commodities) Rules, 2011 - {rule['rule_clause']}",
            "source": field_data.get("source", "ocr"),
            "confidence": field_data.get("confidence", 0.0),
            "fusion_case": field_data.get("fusion_case"),
            "conflict": field_data.get("conflict", False),
        })

    # Determine 3-State Verdict based on Mandatory Rules
    mandatory_inconclusive_count = sum(
        1 for r in rule_results if r["is_mandatory"] and r["status"] == "INCONCLUSIVE"
    )

    if failed_count > 0:
        overall_status = "POTENTIAL NON-COMPLIANCE"
        verdict_color = "danger"
        verdict_title = "Potential Non-Compliance Flagged"
        reason = f"System identified {failed_count} mandatory declaration requirement(s) that appear unfulfilled or missing based on label evidence."
        action_required = "Please inspect the package artwork or request additional label evidence."

    elif mandatory_inconclusive_count > 0:
        overall_status = "INCONCLUSIVE"
        verdict_title = "Inconclusive Assessment"
        verdict_color = "warning"
        reason = "Available evidence is inconclusive to verify all mandatory legal declarations."
        action_required = "Please capture secondary photographs (back/side label) or retake under clearer lighting."

    else:
        overall_status = "COMPLIANT"
        verdict_title = "Preliminary Legal Metrology Compliance Confirmed"
        verdict_color = "success"
        reason = "All applicable mandatory declarations specified under Rule 6 of Legal Metrology (Packaged Commodities) Rules 2011 were successfully verified."
        action_required = "None. Product meets mandatory declaration requirements."

    return {
        "overall_status": overall_status,
        "verdict_title": verdict_title,
        "verdict_color": verdict_color,
        "reason": reason,
        "action_required": action_required,
        "rules_applied_count": len(rule_results),
        "passed_rules_count": passed_count,
        "failed_rules_count": failed_count,
        "inconclusive_rules_count": inconclusive_count,
        "rule_results": rule_results,
        "extracted_evidence": extracted_data
    }
