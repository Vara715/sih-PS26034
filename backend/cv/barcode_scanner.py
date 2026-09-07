"""
Barcode and QR Code Detection Module
------------------------------------
Detects 1D retail barcodes (EAN-13, UPC, Code 128) and 2D QR codes on packaged commodities
using native OpenCV algorithms without requiring external C-libraries (such as zbar).
"""

from typing import Dict, Any, List
import numpy as np

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


def scan_barcodes_and_qr(image_bytes: bytes) -> Dict[str, Any]:
    """
    Analyzes raw image bytes to locate and decode 1D product barcodes and 2D QR codes.
    Returns structured code metadata including code type and payload.
    """
    if not OPENCV_AVAILABLE or not image_bytes:
        return {
            "detected": False,
            "qr_codes": [],
            "barcodes": [],
            "raw_codes": [],
            "message": "Barcode scanning unavailable or empty image."
        }

    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {
                "detected": False,
                "qr_codes": [],
                "barcodes": [],
                "raw_codes": [],
                "message": "Image decode failed."
            }

        qr_codes = []
        barcodes = []
        raw_codes = []

        # 1. 2D QR Code Detection
        try:
            qr_detector = cv2.QRCodeDetector()
            has_multi = hasattr(qr_detector, "detectAndDecodeMulti")
            if has_multi:
                retval, decoded_info, points, _ = qr_detector.detectAndDecodeMulti(img)
                if retval and decoded_info:
                    for text in decoded_info:
                        clean = text.strip()
                        if clean and clean not in raw_codes:
                            qr_codes.append({"type": "QR_CODE", "data": clean})
                            raw_codes.append(clean)

            if not qr_codes:
                text, points, _ = qr_detector.detectAndDecode(img)
                clean = text.strip() if text else ""
                if clean and clean not in raw_codes:
                    qr_codes.append({"type": "QR_CODE", "data": clean})
                    raw_codes.append(clean)
        except Exception:
            pass

        # 2. 1D Barcode Detection (EAN-13, UPC-A, Code-128)
        try:
            if hasattr(cv2, "barcode") and hasattr(cv2.barcode, "BarcodeDetector"):
                barcode_detector = cv2.barcode.BarcodeDetector()
                res = barcode_detector.detectAndDecode(img)
                if res and len(res) >= 1:
                    decoded_info = res[0]
                    if isinstance(decoded_info, (list, tuple)):
                        for code in decoded_info:
                            code_str = str(code).strip()
                            if code_str and code_str not in raw_codes:
                                btype = "EAN_13" if len(code_str) == 13 else "BARCODE"
                                barcodes.append({"type": btype, "data": code_str})
                                raw_codes.append(code_str)
                    elif isinstance(decoded_info, str) and decoded_info.strip():
                        code_str = decoded_info.strip()
                        if code_str not in raw_codes:
                            btype = "EAN_13" if len(code_str) == 13 else "BARCODE"
                            barcodes.append({"type": btype, "data": code_str})
                            raw_codes.append(code_str)
        except Exception:
            pass

        total_detected = len(raw_codes) > 0
        msg = f"Detected {len(barcodes)} barcode(s) and {len(qr_codes)} QR code(s)." if total_detected else "No barcode or QR code detected on visible package face."

        return {
            "detected": total_detected,
            "qr_codes": qr_codes,
            "barcodes": barcodes,
            "raw_codes": raw_codes,
            "message": msg
        }
    except Exception as e:
        return {
            "detected": False,
            "qr_codes": [],
            "barcodes": [],
            "raw_codes": [],
            "message": f"Barcode scan error: {str(e)}"
        }
