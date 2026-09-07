"""
Automated Legal Metrology PDF Inspection Report Generator
----------------------------------------------------------
Generates official, tamper-evident PDF Inspection Audit Certificates
using pure Python standard library without requiring external heavy C-libraries.
"""

from typing import Dict, Any
from datetime import datetime


def _escape_pdf_text(text: str) -> str:
    """Escapes special PDF characters and replaces unsupported unicode with ASCII equivalents."""
    if not text:
        return ""
    # Replace Indian Rupee symbol with Rs. and clean non-latin1 characters
    clean = str(text).replace("₹", "Rs. ").replace("•", "-").replace("✓", "[PASS]").replace("✗", "[FAIL]")
    # Remove control characters and non-printable characters
    clean = "".join(ch if 32 <= ord(ch) <= 126 else " " for ch in clean)
    clean = clean.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return clean[:95]  # limit line length to avoid overflow


def generate_inspection_pdf(scan_data: Dict[str, Any]) -> bytes:
    """
    Constructs a valid PDF-1.4 binary certificate for an inspection record.
    """
    inspection_id = scan_data.get("inspection_id", "INS-UNKNOWN")
    compliance = scan_data.get("compliance_report", {})
    overall_status = compliance.get("overall_status", "PENDING")
    verdict_title = compliance.get("verdict_title", "Preliminary Compliance Assessment")
    rule_results = compliance.get("rule_results", [])
    quality = scan_data.get("quality_assessment", {})
    evidence_ledger = scan_data.get("evidence_ledger") or {}
    evidence_hash = evidence_ledger.get("evidence_hash", "N/A")

    category = scan_data.get("product_category", "packaged_goods").replace("_", " ").title()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Build PDF Content Stream
    stream_lines = []

    # Title & Banner
    stream_lines.append("BT")
    stream_lines.append("/F1 15 Tf 50 745 Td (GOVERNMENT OF INDIA - DEPT. OF CONSUMER AFFAIRS) Tj")
    stream_lines.append("ET")

    stream_lines.append("BT")
    stream_lines.append("/F1 12 Tf 50 728 Td (LEGAL METROLOGY \\(PACKAGED COMMODITIES\\) RULES, 2011) Tj")
    stream_lines.append("ET")

    stream_lines.append("BT")
    stream_lines.append("/F1 10 Tf 50 712 Td (OFFICIAL STATUTORY COMPLIANCE INSPECTION CERTIFICATE) Tj")
    stream_lines.append("ET")

    # Horizontal Divider
    stream_lines.append("0.5 w 50 702 m 562 702 l S")

    # Metadata Block
    y = 685
    stream_lines.append("BT /F1 9 Tf")
    stream_lines.append(f"50 {y} Td (Inspection ID: {inspection_id}     | Category: {category}     | Timestamp: {now_str}) Tj")
    y -= 14
    stream_lines.append(f"50 {y} Td (Evidence Hash \\(SHA-256\\): {_escape_pdf_text(evidence_hash)}) Tj")
    y -= 14
    stream_lines.append(f"50 {y} Td (Blur Score: {quality.get('blur_score', 'N/A')} | Rating: {quality.get('quality_rating', 'N/A')} | Resolution: {quality.get('resolution', 'N/A')}) Tj")
    stream_lines.append("ET")

    # Verdict Box
    y -= 18
    stream_lines.append(f"0.5 w 50 {y-18} 512 28 re S")
    stream_lines.append("BT")
    stream_lines.append(f"/F1 11 Tf 60 {y-5} Td (OVERALL VERDICT: {_escape_pdf_text(overall_status)} - {_escape_pdf_text(verdict_title)}) Tj")
    stream_lines.append("ET")

    # Table Header
    y -= 40
    stream_lines.append(f"0.5 w 50 {y-14} 512 16 re S")
    stream_lines.append("BT")
    stream_lines.append(f"/F1 8 Tf 55 {y-10} Td (RULE CLAUSE       DECLARATION TARGET           STATUS          EXTRACTED EVIDENCE) Tj")
    stream_lines.append("ET")

    # Rule Rows
    y -= 26
    for r in rule_results[:14]:
        if y < 105:
            break
        clause = (r.get("rule_clause", "") + " " * 16)[:16]
        field = (r.get("target_field", "") + " " * 22)[:22]
        status = (r.get("status", "") + " " * 14)[:14]
        raw_ev = r.get("evidence_text")
        if not raw_ev or str(raw_ev).strip().lower() in ("none", "null", ""):
            raw_ev = r.get("explanation") or "Not declared"
            if str(raw_ev).strip().lower() in ("none", "null", ""):
                raw_ev = "Not declared"

        src = r.get("source")
        src_tag = ""
        if src == "gemini":
            src_tag = "[GEM] "
        elif src == "ocr+gemini":
            src_tag = "[OCR+G] "
        elif src == "ocr":
            src_tag = "[OCR] "

        ev_text = _escape_pdf_text(f"{src_tag}{raw_ev}".strip())[:38]

        row_str = f"{clause} {field} {status} {ev_text}"
        stream_lines.append("BT")
        stream_lines.append(f"/F1 8 Tf 55 {y} Td ({row_str}) Tj")
        stream_lines.append("ET")
        y -= 14

    # Footer Disclaimer
    stream_lines.append("0.5 w 50 85 m 562 85 l S")
    stream_lines.append("BT /F1 7 Tf")
    stream_lines.append("50 72 Td (Statutory Disclaimer: This automated audit report provides preliminary compliance assessment under Legal Metrology Rules, 2011.) Tj")
    stream_lines.append("50 62 Td (Final regulatory enforcement is subject to physical verification by an authorized Legal Metrology Officer under the Legal Metrology Act, 2009.) Tj")
    stream_lines.append("ET")

    content_stream = "\n".join(stream_lines) + "\n"
    stream_bytes = content_stream.encode("latin-1", "replace")
    stream_len = len(stream_bytes)

    # PDF Object Graph
    objects = []
    objects.append("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append("2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objects.append(f"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n")
    objects.append(f"4 0 obj\n<< /Length {stream_len} >>\nstream\n{content_stream}endstream\nendobj\n")
    objects.append("5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    body = "%PDF-1.4\n"
    xref = ["xref\n0 6\n0000000000 65535 f \n"]
    pos = len(body.encode("latin-1"))

    for obj in objects:
        xref.append(f"{pos:010d} 00000 n \n")
        body += obj
        pos = len(body.encode("latin-1"))

    xref_pos = pos
    body += "".join(xref)
    body += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"

    return body.encode("latin-1")
