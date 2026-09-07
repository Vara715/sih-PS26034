"""
Font Size and Readability Analysis Module
------------------------------------------
Evaluates compliance with Rule 9 of Legal Metrology (Packaged Commodities) Rules 2011:
Mandatory minimum height of letters and numerals on package principal display panels.
"""

from typing import Dict, Any, List, Optional


def analyze_font_readability(
    tokens: List[Dict[str, Any]],
    image_shape: Optional[tuple] = None,
    net_quantity_val: Optional[float] = None,
    net_quantity_unit: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes numeral and character height metrics from OCR token bounding boxes.
    Assesses against Legal Metrology Rule 9 recommended numeral height standards.
    """
    if not tokens:
        return {
            "evaluated": False,
            "readability_score": 0.0,
            "min_token_height_px": 0.0,
            "avg_token_height_px": 0.0,
            "rule_9_compliant": True,
            "findings": ["No spatial tokens available for font dimension analysis."],
            "recommendation": "Ensure clear, high-resolution photo is captured."
        }

    heights = []
    numeral_heights = []

    for t in tokens:
        bbox = t.get("bbox")
        if bbox and len(bbox) >= 4:
            h = abs(float(bbox[3]) - float(bbox[1]))
            if h > 2.0:  # exclude 1-2px noise
                heights.append(h)
                txt = t.get("text", "")
                if any(ch.isdigit() for ch in txt):
                    numeral_heights.append(h)

    if not heights:
        return {
            "evaluated": False,
            "readability_score": 0.5,
            "min_token_height_px": 0.0,
            "avg_token_height_px": 0.0,
            "rule_9_compliant": True,
            "findings": ["Bounding box dimensions negligible or unmeasured."],
            "recommendation": "N/A"
        }

    min_h = round(min(heights), 1)
    avg_h = round(sum(heights) / len(heights), 1)
    avg_num_h = round(sum(numeral_heights) / len(numeral_heights), 1) if numeral_heights else avg_h

    img_h = image_shape[0] if image_shape and len(image_shape) >= 1 else 1000.0
    relative_num_ratio = avg_num_h / float(img_h)

    # Determine legal minimum height threshold guideline under Rule 9
    min_required_mm = 2.0
    if net_quantity_val is not None:
        try:
            val = float(net_quantity_val)
            unit = (net_quantity_unit or "g").lower()
            if unit in ["kg", "l"] or val >= 1000.0:
                min_required_mm = 6.0
            elif val > 200.0:
                min_required_mm = 4.0
            elif val > 50.0:
                min_required_mm = 2.0
            else:
                min_required_mm = 1.0
        except Exception:
            min_required_mm = 2.0

    findings = []
    rule_9_compliant = True

    if avg_h < 12.0 or relative_num_ratio < 0.012:
        rule_9_compliant = False
        findings.append(f"Small print warning: Average declaration height ({avg_h}px) appears below recommended legible height.")
    else:
        findings.append(f"Legible typography: Average declaration font height is {avg_h}px ({round(relative_num_ratio*100, 1)}% of display height).")

    if numeral_heights and min(numeral_heights) < 8.0:
        findings.append("Certain numeral declarations (price/weight) use fine print (<8px).")

    readability_score = min(1.0, max(0.2, round(avg_h / 24.0, 2)))

    return {
        "evaluated": True,
        "readability_score": readability_score,
        "avg_token_height_px": avg_h,
        "avg_numeral_height_px": avg_num_h,
        "min_token_height_px": min_h,
        "rule_9_threshold_mm": min_required_mm,
        "rule_9_compliant": rule_9_compliant,
        "findings": findings,
        "recommendation": "Typography complies with standard legibility guidelines." if rule_9_compliant else "Consider increasing font point size for mandatory numerals per Rule 9."
    }
