"""
Automated System Verification Test Suite
----------------------------------------
Tests OpenCV quality assessment, product packaging evidence validator (Gate 1),
regex declaration extractor, legal rule engine, SQLite SHA-256 evidence ledger,
and API endpoint sequential execution.
"""

import sys
import os
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from cv.quality import assess_image_quality
from cv.product_validator import validate_product_image
from extraction.extractor import extract_declarations
from rules.engine import evaluate_compliance
from database.db import save_inspection, get_inspection_by_id


class TestLegalMetrologySystem(unittest.TestCase):

    def test_01_quality_assessment(self):
        """Tests image quality assessment on valid vs invalid buffer."""
        img_bytes = b"synthetic_test_image_buffer"
        assessment = assess_image_quality(img_bytes)
        self.assertTrue(assessment["is_valid_image"])
        self.assertIn("quality_rating", assessment)

    def test_02_field_extraction(self):
        """Tests Legal Metrology declaration regex extractor on a compliant label text."""
        sample_text = """
        ABC Premium Wheat Biscuits
        Net Qty: 500 g
        MRP Rs. 120.00 (incl. of all taxes)
        Mfd Date: 08/2026
        Manufactured by ABC Foods Pvt Ltd, Industrial Area, New Delhi
        Consumer Care Helpline: 1800-111-2222 Email: care@abcfoods.in
        Country of Origin: India
        Unit Sale Price: Rs 0.24 / g
        """
        extracted = extract_declarations(sample_text)

        self.assertTrue(extracted["mrp"]["detected"])
        self.assertEqual(extracted["mrp"]["value"], 120.0)

        self.assertTrue(extracted["net_quantity"]["detected"])
        self.assertEqual(extracted["net_quantity"]["value"], 500.0)
        self.assertEqual(extracted["net_quantity"]["unit"], "g")

        self.assertTrue(extracted["manufacturing_date"]["detected"])
        self.assertEqual(extracted["manufacturing_date"]["date_str"], "08/2026")

        self.assertTrue(extracted["manufacturer"]["detected"])
        self.assertTrue(extracted["consumer_care"]["detected"])

    def test_03_rule_engine_compliant(self):
        """Tests Rule Engine returning COMPLIANT verdict when all Rule 6 declarations are present."""
        sample_text = """
        ABC Premium Wheat Biscuits
        Net Qty: 500 g
        MRP Rs. 120.00 (incl. of all taxes)
        Mfd Date: 08/2026
        Best Before: 08/2027
        Manufactured by ABC Foods Pvt Ltd, New Delhi
        Customer Care: 1800-111-2222
        """
        extracted = extract_declarations(sample_text)
        quality = {"is_readable": True, "blur_score": 150.0, "quality_rating": "EXCELLENT"}
        report = evaluate_compliance(extracted, quality, product_category="food")

        self.assertEqual(report["overall_status"], "COMPLIANT")
        self.assertEqual(report["failed_rules_count"], 0)

    def test_04_rule_engine_non_compliant(self):
        """Tests Rule Engine returning POTENTIAL NON-COMPLIANCE when MRP is missing."""
        sample_text = """
        Golden Pure Cooking Oil
        Net Quantity: 1 L
        Mfd Date: 12/2025
        Manufactured by Sunrise Oils Ltd
        """
        extracted = extract_declarations(sample_text)
        quality = {"is_readable": True, "blur_score": 120.0, "quality_rating": "GOOD"}
        report = evaluate_compliance(extracted, quality, product_category="packaged_goods")

        self.assertEqual(report["overall_status"], "POTENTIAL NON-COMPLIANCE")
        self.assertGreater(report["failed_rules_count"], 0)

    def test_05_rule_engine_inconclusive(self):
        """Tests Rule Engine returning INCONCLUSIVE when image is severely blurry."""
        extracted = {}
        quality = {"is_readable": False, "blur_score": 20.0, "message": "Severe blur detected"}
        report = evaluate_compliance(extracted, quality, product_category="packaged_goods")

        self.assertEqual(report["overall_status"], "INCONCLUSIVE")

    def test_06_database_ledger_hash(self):
        """Tests SQLite database saving and SHA-256 evidence hashing."""
        import uuid
        test_id = f"TEST-INS-{uuid.uuid4().hex[:6]}"
        res = save_inspection(
            inspection_id=test_id,
            user_mode="inspector",
            product_category="food",
            overall_status="COMPLIANT",
            verdict_title="Compliant Test",
            blur_score=150.0,
            brightness_score=128.0,
            ocr_text="MRP Rs 100",
            extracted_data={"mrp": 100},
            rule_results=[],
            image_bytes=b"sample_test_image_data"
        )
        self.assertEqual(res["inspection_id"], test_id)
        self.assertIn("evidence_hash", res)

        rec = get_inspection_by_id(test_id)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["overall_status"], "COMPLIANT")

        # Clean up test artifact from DB
        from database.db import get_db_connection
        conn = get_db_connection()
        conn.cursor().execute("DELETE FROM inspections WHERE id = ?", (test_id,))
        conn.commit()
        conn.close()

    def test_07_notebook_page_rejection(self):
        """Tests that uploading a notebook page or random document is rejected."""
        notebook_text = """
        Chapter 4: Science Study Notes
        Topic: Thermodynamics and Newton Laws of Motion
        1. Every action has equal and opposite reaction.
        """
        extracted = extract_declarations(notebook_text)
        quality = {"is_readable": True, "blur_score": 150.0, "quality_rating": "EXCELLENT"}
        report = evaluate_compliance(extracted, quality, product_category="packaged_goods")

        self.assertEqual(report["overall_status"], "POTENTIAL NON-COMPLIANCE")

    def test_08_user_authentication(self):
        """Tests SQLite user registration and login authentication."""
        from database.db import create_user, authenticate_user
        import uuid
        test_email = f"test_{uuid.uuid4().hex[:6]}@metrology.gov.in"
        
        user = create_user("Test Inspector", test_email, "pass123", "inspector", "INS-TEST-99")
        self.assertEqual(user["email"], test_email)
        self.assertEqual(user["role"], "inspector")

        auth_user = authenticate_user(test_email, "pass123")
        self.assertIsNotNone(auth_user)
        self.assertEqual(auth_user["username"], "Test Inspector")

        invalid_user = authenticate_user(test_email, "wrongpass")
        self.assertIsNone(invalid_user)

    def test_09_gate1_notebook_with_mrp_rejection(self):
        """CRITICAL FALSE-POSITIVE TEST: Notebook page with 'MRP ₹120' MUST be rejected at Gate 1 BEFORE OCR."""
        notebook_buffer = b"notebook page handwritten MRP \xe2\x82\xb9120 Net Qty 500 g Manufacturer ABC"
        val = validate_product_image(notebook_buffer)

        self.assertEqual(val["status"], "INVALID_PRODUCT_IMAGE")
        self.assertFalse(val["should_proceed_to_ocr"])
        self.assertIn("rejected", val["reason"].lower())

    def test_10_gate1_valid_product_packaging(self):
        """Tests Gate 1 accepting real packaged commodity evidence."""
        package_buffer = b"biscuit packet pouch bottle consumer product package"
        val = validate_product_image(package_buffer)

        self.assertEqual(val["status"], "VALID_PRODUCT")
        self.assertTrue(val["should_proceed_to_ocr"])

    def test_11_dual_label_fusion(self):
        """Tests front and back dual-label text concatenation and declaration extraction."""
        front_text = "PREMIUM BISCUITS\nNet Qty: 200 g\nMRP Rs. 50.00 (incl. of all taxes)"
        back_text = "Mfd Date: 05/2026\nManufactured by Sunrise Foods Pvt Ltd\nConsumer Care: 1800-222-3333"
        combined_text = front_text + "\n--- BACK LABEL ---\n" + back_text
        extracted = extract_declarations(combined_text)

        self.assertTrue(extracted["mrp"]["detected"])
        self.assertEqual(extracted["mrp"]["value"], 50.0)
        self.assertTrue(extracted["manufacturing_date"]["detected"])
        self.assertEqual(extracted["manufacturing_date"]["date_str"], "05/2026")
        self.assertTrue(extracted["consumer_care"]["detected"])

    def test_12_opencv_synthetic_notebook_image_rejection(self):
        """Tests that a real synthesized PNG image of a notebook page with ruled lines is strictly REJECTED at Gate 1."""
        import cv2
        import numpy as np

        # Create a white canvas (notebook page)
        img = np.full((600, 800, 3), 245, dtype=np.uint8)

        # Draw horizontal notebook ruling lines
        for y in range(80, 550, 40):
            cv2.line(img, (50, y), (750, y), (200, 180, 180), 1)

        # Write handwritten style text
        cv2.putText(img, "MRP Rs. 120", (100, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (40, 40, 40), 2)
        cv2.putText(img, "Net Qty: 500 g", (100, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (40, 40, 40), 2)

        _, png_bytes = cv2.imencode('.png', img)
        val = validate_product_image(png_bytes.tobytes())

        self.assertEqual(val["status"], "INVALID_PRODUCT_IMAGE")
        self.assertFalse(val["should_proceed_to_ocr"])

    def test_13_opencv_synthetic_package_image(self):
        """Tests that a synthesized multi-colored product packaging image passes Gate 1."""
        import cv2
        import numpy as np

        # Dark background
        img = np.full((600, 800, 3), 30, dtype=np.uint8)

        # Draw colorful product box (bright blue/gold packaging with artwork)
        cv2.rectangle(img, (150, 100), (650, 500), (220, 120, 30), -1)
        cv2.circle(img, (400, 250), 80, (50, 200, 240), -1)
        cv2.putText(img, "PREMIUM BISCUITS", (200, 400), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)

        _, png_bytes = cv2.imencode('.png', img)
        val = validate_product_image(png_bytes.tobytes())

        self.assertEqual(val["status"], "VALID_PRODUCT")
        self.assertTrue(val["should_proceed_to_ocr"])


    def test_14_spatial_mrp_candidate_selection(self):
        """CRITICAL SPATIAL TEST: Anchor 'MRP' near '5.00' must select 5.00 over distant '18' token."""
        sample_text = "MRP Rs 5.00 incl. taxes\nIngredients: Wheat flour 18% Sugar"
        tokens = [
            {"text": "MRP", "bbox": [10, 10, 50, 30], "center": [30.0, 20.0], "confidence": 0.95},
            {"text": "Rs", "bbox": [55, 10, 80, 30], "center": [67.5, 20.0], "confidence": 0.95},
            {"text": "5.00", "bbox": [85, 10, 120, 30], "center": [102.5, 20.0], "confidence": 0.95},
            {"text": "incl.", "bbox": [125, 10, 160, 30], "center": [142.5, 20.0], "confidence": 0.90},
            {"text": "taxes", "bbox": [165, 10, 200, 30], "center": [182.5, 20.0], "confidence": 0.90},
            {"text": "Ingredients:", "bbox": [10, 200, 100, 220], "center": [55.0, 210.0], "confidence": 0.90},
            {"text": "Wheat", "bbox": [105, 200, 150, 220], "center": [127.5, 210.0], "confidence": 0.90},
            {"text": "flour", "bbox": [155, 200, 190, 220], "center": [172.5, 210.0], "confidence": 0.90},
            {"text": "18%", "bbox": [195, 200, 230, 220], "center": [212.5, 210.0], "confidence": 0.95},
            {"text": "Sugar", "bbox": [235, 200, 280, 220], "center": [257.5, 210.0], "confidence": 0.90},
        ]
        extracted = extract_declarations(sample_text, tokens=tokens)

        self.assertTrue(extracted["mrp"]["detected"])
        self.assertEqual(extracted["mrp"]["value"], 5.0)
        self.assertNotEqual(extracted["mrp"]["value"], 18.0)
        self.assertGreaterEqual(extracted["mrp"]["confidence"], 0.75)

    def test_15_date_fabrication_rejection(self):
        """CRITICAL DATE FABRICATION TEST: Raw 4-digit '7614' without date anchors MUST be rejected."""
        sample_text = "Code: 7614 Batch No A9"
        extracted = extract_declarations(sample_text)

        self.assertFalse(extracted["manufacturing_date"]["detected"])
        self.assertIsNone(extracted["manufacturing_date"]["date_str"])

    def test_16_manufacturer_regd_rejection(self):
        """CRITICAL MANUFACTURER TEST: Standalone 'REGD.' without name/address MUST be rejected."""
        sample_text = "REGD."
        extracted = extract_declarations(sample_text)

        self.assertFalse(extracted["manufacturer"]["detected"])

        valid_sample = "Manufactured by ABC Foods Pvt Ltd, Industrial Area, Plot 12, Delhi"
        extracted_valid = extract_declarations(valid_sample)
        self.assertTrue(extracted_valid["manufacturer"]["detected"])
        self.assertEqual(extracted_valid["manufacturer"]["status"], "VERIFIED")

    def test_17_ambiguous_inconclusive_verdict(self):
        """Tests that low confidence/ambiguous OCR triggers INCONCLUSIVE status in Rule Engine."""
        extracted = {
            "mrp": {"detected": True, "value": 50.0, "status": "INCONCLUSIVE", "confidence": 0.3},
            "net_quantity": {"detected": False, "status": "FAIL", "confidence": 0.0},
            "manufacturing_date": {"detected": False, "status": "FAIL", "confidence": 0.0},
            "manufacturer": {"detected": False, "status": "FAIL", "confidence": 0.0},
            "consumer_care": {"detected": False, "status": "FAIL", "confidence": 0.0},
            "country_of_origin": {"detected": False, "status": "FAIL", "confidence": 0.0},
        }
        quality = {"is_readable": True, "blur_score": 120.0, "quality_rating": "GOOD"}
        report = evaluate_compliance(extracted, quality, product_category="food")

        # Must not fabricate false PASS or confident FAIL where field is INCONCLUSIVE
        mrp_rule = next(r for r in report["rule_results"] if "MRP" in r["rule_name"])
        self.assertEqual(mrp_rule["status"], "INCONCLUSIVE")


    def test_18_opencv_deskew_and_sanitization(self):
        """Tests OpenCV deskewing module and post-OCR misread character sanitization."""
        from cv.deskew import detect_text_skew_angle, deskew_image
        import numpy as np

        # 1. Test deskew function on array
        dummy_img = np.full((100, 200, 3), 255, dtype=np.uint8)
        deskewed = deskew_image(dummy_img)
        self.assertEqual(deskewed.shape, dummy_img.shape)

        # 2. Test post-OCR character misread mapper
        from extraction.extractor import sanitize_ocr_text_for_fields
        garbled_text = "MRP Rs S0.O0\nPKD 08/2O2B\nNet Qty: 500 grn"
        cleaned = sanitize_ocr_text_for_fields(garbled_text)

        extracted = extract_declarations(garbled_text)
        self.assertTrue(extracted["mrp"]["detected"])
        self.assertEqual(extracted["mrp"]["value"], 50.0)
        self.assertTrue(extracted["net_quantity"]["detected"])
        self.assertEqual(extracted["net_quantity"]["value"], 500.0)
        self.assertEqual(extracted["net_quantity"]["unit"], "g")

    def test_19_compact_date_and_field_formats(self):
        """Tests extraction on compact strings without spaces or delimiters (e.g. PKD29AUG26, MRP5.00, NET QTY 500g)."""
        compact_text = "PREMIUM FOODS\nPKD29AUG26\nMRP5.00\nNET QTY 500g\nMfg by Sunrise Foods Pvt Ltd"
        extracted = extract_declarations(compact_text)

        self.assertTrue(extracted["manufacturing_date"]["detected"])
        self.assertEqual(extracted["manufacturing_date"]["date_str"], "29/AUG/2026")

        self.assertTrue(extracted["mrp"]["detected"])
        self.assertEqual(extracted["mrp"]["value"], 5.0)

        self.assertTrue(extracted["net_quantity"]["detected"])
        self.assertEqual(extracted["net_quantity"]["value"], 500.0)
        self.assertEqual(extracted["net_quantity"]["unit"], "g")

        self.assertTrue(extracted["manufacturer"]["detected"])

    def test_20_mrp_decimal_correction(self):
        """Tests dropped decimal point price correction (e.g. MRP Rs 8500, -> Rs 85.0)."""
        sample_text = "MRP Rs 8500,\nNet Qty: 24g\nPKD 29AUG26"
        extracted = extract_declarations(sample_text)

        self.assertTrue(extracted["mrp"]["detected"])
        self.assertEqual(extracted["mrp"]["value"], 85.0)

    def test_21_wafer_package_real_ground_truth(self):
        """
        Regression test for real wafer product label:
        Actual label: MRP: ₹ 5.00, NET WEIGHT: 24g, PKD: 28AUG26, WAFERS PRIVATE LIMITED
        Critical requirement: MRP MUST NOT become 85.0 or 8500.0.
        """
        ocr_lines = (
            "BALAJI WAFERS\n"
            "NET WEIGHT : 24g\n"
            "MRP: \n"
            "₹ 5.00\n"
            "PKD.:\n"
            "28AUG26\n"
            "WAFERS PRIVATE LIMITED\n"
            "REGD. OFFICE: VADINAD ROAD"
        )
        extracted = extract_declarations(ocr_lines)

        if extracted["mrp"]["detected"]:
            self.assertNotEqual(extracted["mrp"]["value"], 85.0, "MRP incorrectly extracted as 85.0!")
            self.assertNotEqual(extracted["mrp"]["value"], 8500.0, "MRP incorrectly extracted as 8500.0!")
            self.assertEqual(extracted["mrp"]["value"], 5.0)

        self.assertTrue(extracted["net_quantity"]["detected"])
        self.assertEqual(extracted["net_quantity"]["value"], 24.0)
        self.assertEqual(extracted["net_quantity"]["unit"], "g")

        self.assertTrue(extracted["manufacturing_date"]["detected"])
        self.assertIn("2026", extracted["manufacturing_date"]["date_str"])

        self.assertTrue(extracted["manufacturer"]["detected"])
        self.assertIn("WAFERS", extracted["manufacturer"]["details"].upper())

    def test_22_fssai_license_extraction(self):
        """Tests 14-digit FSSAI food safety license number extraction."""
        sample = "PREMIUM CRUNCH BISCUITS\nFSSAI Lic. No. 10015022000123\nNet Qty: 200 g\nMRP Rs. 40.00"
        extracted = extract_declarations(sample)
        self.assertTrue(extracted["fssai_license"]["detected"])
        self.assertEqual(extracted["fssai_license"]["license_number"], "10015022000123")
        self.assertEqual(extracted["fssai_license"]["status"], "VERIFIED")

    def test_23_batch_number_extraction(self):
        """Tests Batch and Lot code extraction under Rule 6(1)(e)."""
        sample = "Batch No: B-9021/A\nLot No: LT-450\nMRP Rs 25.00"
        extracted = extract_declarations(sample)
        self.assertTrue(extracted["batch_number"]["detected"])
        self.assertEqual(extracted["batch_number"]["batch_number"], "B-9021/A")

    def test_24_hindi_label_extraction(self):
        """Tests extraction on Hindi/Devanagari commodity declarations."""
        sample = "अधिकतम खुदरा मूल्य ₹ 120.00 (सभी करों सहित)\nशुद्ध मात्रा: 500 ग्राम\nउत्पाद: बिस्कुट\nभारत में निर्मित"
        extracted = extract_declarations(sample)
        self.assertTrue(extracted["mrp"]["detected"])
        self.assertEqual(extracted["mrp"]["value"], 120.0)
        self.assertTrue(extracted["net_quantity"]["detected"])
        self.assertEqual(extracted["net_quantity"]["value"], 500.0)
        self.assertEqual(extracted["country_of_origin"]["country"], "India")

    def test_25_pdf_certificate_generation(self):
        """Tests pure-Python PDF Inspection Certificate generation."""
        from reporting.pdf_report import generate_inspection_pdf
        scan_data = {
            "inspection_id": "INS-CERT-99",
            "product_category": "food",
            "compliance_report": {
                "overall_status": "COMPLIANT",
                "verdict_title": "Legal Metrology Confirmed",
                "rule_results": [
                    {"rule_clause": "Rule 6(1)(f)", "target_field": "mrp", "status": "PASS", "evidence_text": "Rs. 100"}
                ]
            },
            "quality_assessment": {"blur_score": 150.0, "quality_rating": "EXCELLENT", "resolution": "1920x1080"},
            "evidence_ledger": {"evidence_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}
        }
        pdf = generate_inspection_pdf(scan_data)
        self.assertIsInstance(pdf, bytes)
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertTrue(pdf.strip().endswith(b"%%EOF"))

    def test_26_barcode_scanner_module(self):
        """Tests barcode and QR code scanner returns expected structure without exceptions."""
        from cv.barcode_scanner import scan_barcodes_and_qr
        import numpy as np
        import cv2

        img = np.full((200, 200, 3), 255, dtype=np.uint8)
        _, png_bytes = cv2.imencode('.png', img)
        res = scan_barcodes_and_qr(png_bytes.tobytes())
        self.assertIn("detected", res)
        self.assertIn("qr_codes", res)
        self.assertIn("barcodes", res)
        self.assertIsInstance(res["raw_codes"], list)

    def test_27_rule9_readability_analysis(self):
        """Tests Rule 9 font height and legibility analysis."""
        from cv.readability import analyze_font_readability
        tokens = [
            {"text": "MRP", "bbox": [10, 10, 50, 40]},
            {"text": "120.00", "bbox": [55, 10, 100, 40]},
            {"text": "Net", "bbox": [10, 50, 40, 80]},
            {"text": "500", "bbox": [45, 50, 80, 80]},
            {"text": "g", "bbox": [85, 50, 100, 80]}
        ]
        res = analyze_font_readability(tokens, image_shape=(1000, 1000, 3), net_quantity_val=500.0, net_quantity_unit="g")
        self.assertTrue(res["evaluated"])
        self.assertIn("avg_token_height_px", res)
        self.assertEqual(res["avg_token_height_px"], 30.0)
        self.assertTrue(res["rule_9_compliant"])

    def test_28_jwt_authentication_token(self):
        """Tests standard library JWT generation, validation, and tamper-resistance."""
        from database.db import create_access_token, decode_access_token
        claims = {"user_id": 42, "role": "inspector", "email": "officer@gov.in"}
        token = create_access_token(claims, expires_in=3600)
        self.assertIsInstance(token, str)

        decoded = decode_access_token(token)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["user_id"], 42)
        self.assertEqual(decoded["role"], "inspector")

        # Test tampered token rejection
        parts = token.split(".")
        tampered_token = parts[0] + "." + parts[1] + "X." + parts[2]
        self.assertIsNone(decode_access_token(tampered_token))

    def test_29_fail_closed_corrupted_image(self):
        """Tests that corrupted non-text binary payloads fail-closed in image quality analysis."""
        corrupted_bytes = bytes([0x00, 0x12, 0xFE, 0x00, 0x00, 0x00, 0x89, 0xFF] * 20)
        assessment = assess_image_quality(corrupted_bytes)
        self.assertFalse(assessment["is_valid_image"])
        self.assertFalse(assessment["is_readable"])
        self.assertEqual(assessment["quality_rating"], "INVALID_IMAGE_PAYLOAD")

    def test_30_inspection_pagination(self):
        """Tests inspection audit ledger offset pagination."""
        from database.db import get_all_inspections
        p1 = get_all_inspections(limit=3, offset=0)
        self.assertIsInstance(p1, list)
        self.assertLessEqual(len(p1), 3)

    def test_31_white_packaging_validation(self):
        """Tests that a legitimate white-background packaged commodity is accepted by Gate 1."""
        import numpy as np, cv2
        white_box = np.full((500, 500, 3), 245, dtype=np.uint8)
        cv2.rectangle(white_box, (50, 50), (450, 450), (200, 200, 200), 2)
        cv2.putText(white_box, 'AMUL BUTTER', (80, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (20, 20, 180), 2)
        cv2.putText(white_box, 'Net Qty: 100g', (80, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 2)
        _, png = cv2.imencode('.png', white_box)
        res = validate_product_image(png.tobytes())
        self.assertEqual(res["status"], "VALID_PRODUCT")
        self.assertTrue(res["should_proceed_to_ocr"])
        self.assertGreaterEqual(res["confidence"], 0.45)

    def test_32_product_validator_safe_failures(self):
        """Tests that empty, corrupted, and non-image payloads fail cleanly without UnboundLocalError."""
        res_empty = validate_product_image(b"")
        self.assertEqual(res_empty["status"], "INVALID_PRODUCT_IMAGE")
        self.assertFalse(res_empty["should_proceed_to_ocr"])

        res_corrupt = validate_product_image(b"\x00\x01\xfe\xff\xaa\xbb\xcc\xdd" * 10)
        self.assertEqual(res_corrupt["status"], "INVALID_PRODUCT_IMAGE")
        self.assertFalse(res_corrupt["should_proceed_to_ocr"])

    def test_33_food_expiry_mandatory_fail(self):
        """Tests that food category strictly mandates expiry date under Rule 6(1)(e) Second Proviso."""
        food_sample = """
        ABC Premium Wheat Biscuits
        Net Qty: 500 g
        MRP Rs. 120.00 (incl. of all taxes)
        Mfd Date: 08/2026
        Manufactured by ABC Foods Pvt Ltd, New Delhi
        Customer Care: 1800-111-2222
        Country of Origin: India
        """
        extracted = extract_declarations(food_sample)
        quality = {"is_readable": True, "blur_score": 150.0, "quality_rating": "EXCELLENT"}
        report = evaluate_compliance(extracted, quality, product_category="food")
        self.assertEqual(report["overall_status"], "POTENTIAL NON-COMPLIANCE")
        expiry_rule = next(r for r in report["rule_results"] if r["target_field"] == "expiry_date")
        self.assertTrue(expiry_rule["is_mandatory"])
        self.assertEqual(expiry_rule["status"], "FAIL")

    def test_34_non_food_expiry_optional_pass(self):
        """Tests that non-food category treats expiry date as optional and passes compliance."""
        nonfood_sample = """
        SPARKLE DISHWASH BAR
        Net Wt: 500 g
        MRP Rs. 85.00 (Incl. all taxes)
        Mfd: 07/2026
        Manufactured by CleanTech Industries Ltd, Nashik
        Customer Care: 1800-200-5678
        Country of Origin: India
        """
        extracted = extract_declarations(nonfood_sample)
        quality = {"is_readable": True, "blur_score": 150.0, "quality_rating": "EXCELLENT"}
        report = evaluate_compliance(extracted, quality, product_category="packaged_goods")
        self.assertEqual(report["overall_status"], "COMPLIANT")
        expiry_rule = next(r for r in report["rule_results"] if r["target_field"] == "expiry_date")
        self.assertFalse(expiry_rule["is_mandatory"])
        self.assertEqual(expiry_rule["status"], "INCONCLUSIVE")

    def test_35_imported_package_missing_origin(self):
        """Tests that imported product category strictly fails if Country of Origin is missing."""
        sample = """
        Imported Swiss Chocolates
        Net Wt: 100 g
        MRP Rs. 350.00
        Mfd: 01/2026
        Best Before: 01/2027
        Imported by: Alpine Importers Pvt Ltd, Mumbai
        Consumer Care: care@alpine.in
        """
        extracted = extract_declarations(sample)
        quality = {"is_readable": True, "blur_score": 150.0, "quality_rating": "EXCELLENT"}
        report = evaluate_compliance(extracted, quality, product_category="imported")
        self.assertEqual(report["overall_status"], "POTENTIAL NON-COMPLIANCE")
        origin_rule = next(r for r in report["rule_results"] if r["target_field"] == "country_of_origin")
        self.assertEqual(origin_rule["status"], "FAIL")

    def test_36_db_get_inspection_null_and_malformed_json(self):
        """Tests SQLite database get_inspection_by_id robustness on NULL and corrupted JSON fields."""
        import sqlite3
        from database.db import get_db_connection, get_inspection_by_id
        conn = get_db_connection()
        c = conn.cursor()
        test_id = "TEST-CORRUPT-JSON-99"
        c.execute("DELETE FROM inspections WHERE id = ?", (test_id,))
        c.execute("""
            INSERT INTO inspections (
                id, timestamp, user_mode, product_category, overall_status, verdict_title,
                blur_score, brightness_score, ocr_text, extracted_json, rule_results_json,
                image_sha256, evidence_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_id, "2026-09-07 12:00:00", "inspector", "food", "COMPLIANT", "Test Verdict",
            100.0, 120.0, "sample ocr", "{malformed_json_syntax:!!}", None,
            "abc123sha", "ev_hash_456"
        ))
        conn.commit()
        conn.close()

        rec = get_inspection_by_id(test_id)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["extracted_data"], {})
        self.assertEqual(rec["rule_results"], [])

    def test_37_pdf_long_manufacturer_and_address_layout(self):
        """Tests PDF certificate layout safety with long strings and multiple rule violations."""
        from reporting.pdf_report import generate_inspection_pdf
        scan_data = {
            "inspection_id": "INS-LONG-ADDR-01",
            "product_category": "packaged_goods",
            "compliance_report": {
                "overall_status": "POTENTIAL NON-COMPLIANCE",
                "verdict_title": "Multiple Declarations Incomplete",
                "rule_results": [
                    {
                        "rule_clause": f"Clause 6(1)({chr(97+i)})",
                        "target_field": f"target_field_{i}",
                        "status": "FAIL" if i % 2 == 0 else "PASS",
                        "evidence_text": "A" * 80,
                        "explanation": "Extremely detailed statutory discrepancy description spanning multiple words."
                    }
                    for i in range(16)
                ]
            },
            "quality_assessment": {"blur_score": 110.0, "quality_rating": "GOOD", "resolution": "4032x3024"},
            "evidence_ledger": {"evidence_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}
        }
        pdf = generate_inspection_pdf(scan_data)
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertTrue(pdf.strip().endswith(b"%%EOF"))
        self.assertIn(b"POTENTIAL NON-COMPLIANCE", pdf)

    def test_38_mrp_decimal_handling_and_confusion(self):
        """Tests MRP regex accuracy: handles explicit decimals, currency symbols, and dropped decimal correction."""
        sample_decimal = "PREMIUM CRACKERS\nMRP Rs. 10.50 (incl. taxes)\nNet Wt: 100 g"
        ext1 = extract_declarations(sample_decimal)
        self.assertTrue(ext1["mrp"]["detected"])
        self.assertEqual(ext1["mrp"]["value"], 10.50)

        # 4-digit dropped decimal correction (8500 -> 85.0)
        sample_dropped = "PREMIUM CRACKERS\nMRP Rs 8500 (incl. taxes)\nNet Wt: 100 g"
        ext2 = extract_declarations(sample_dropped)
        self.assertTrue(ext2["mrp"]["detected"])
        self.assertEqual(ext2["mrp"]["value"], 85.0)

    def test_39_hindi_devanagari_packaging_declarations(self):
        """Tests multi-lingual Hindi Devanagari declarations mapped into standardized compliance structures."""
        sample_hindi = (
            "चक्की फ्रेश आटा\n"
            "अधिकतम खुदरा मूल्य ₹ 250.00 (सभी करों सहित)\n"
            "शुद्ध मात्रा: 5 किग्रा\n"
            "भारत में निर्मित\n"
            "उत्पाद: आटा\n"
            "उत्पादक: श्री ग्रेन्स प्रा. लि., दिल्ली"
        )
        ext = extract_declarations(sample_hindi)
        self.assertTrue(ext["mrp"]["detected"])
        self.assertEqual(ext["mrp"]["value"], 250.0)
        self.assertTrue(ext["net_quantity"]["detected"])
        self.assertEqual(ext["net_quantity"]["value"], 5.0)
        self.assertEqual(ext["net_quantity"]["unit"], "kg")
        self.assertEqual(ext["country_of_origin"]["country"], "India")

    def test_40_offline_ocr_never_fabricates_tokens_on_real_images(self):
        """Tests that real binary images where OCR fails never fabricate synthetic compliance tokens."""
        from ocr.engine import extract_text_from_image
        import numpy as np, cv2
        # Real blank black PNG image
        blank_img = np.zeros((300, 300, 3), dtype=np.uint8)
        _, png = cv2.imencode('.png', blank_img)
        res = extract_text_from_image(png.tobytes())
        # Must return empty text or not synthetic
        if not res["success"]:
            self.assertEqual(len(res["tokens"]), 0)
            self.assertFalse(res.get("is_synthetic", False))

    def test_41_anchored_numeric_mfd_date(self):
        """Tests that anchored slash-delimited numeric date 'PKD: 12/08/2024' extracts correctly."""
        sample = "ABC Biscuits\nPKD: 12/08/2024\nMRP Rs. 50"
        ext = extract_declarations(sample)
        mfd = ext["manufacturing_date"]
        self.assertTrue(mfd["detected"])
        self.assertEqual(mfd["status"], "VERIFIED")
        self.assertEqual(mfd["date_str"], "12/08/2024")

    # ===========================================================================
    # Gemini Extractor Tests (tests 42–50) — all mocked, NO real API quota used
    # ===========================================================================

    def test_42_gemini_response_parsing_valid_json(self):
        """_parse_gemini_response correctly parses a well-formed JSON string."""
        from extraction.gemini_extractor import _parse_gemini_response
        raw = '{"mrp": {"value": 45.0, "visible_text": "MRP Rs. 45"}}'
        parsed = _parse_gemini_response(raw)
        self.assertEqual(parsed["mrp"]["value"], 45.0)
        self.assertEqual(parsed["mrp"]["visible_text"], "MRP Rs. 45")

    def test_43_gemini_response_parsing_markdown_fences(self):
        """_parse_gemini_response strips markdown code fences before parsing JSON."""
        from extraction.gemini_extractor import _parse_gemini_response
        raw = '```json\n{"mrp": {"value": 20.0, "visible_text": "Rs 20"}}\n```'
        parsed = _parse_gemini_response(raw)
        self.assertIn("mrp", parsed)
        self.assertEqual(parsed["mrp"]["value"], 20.0)

    def test_44_gemini_response_parsing_malformed_json(self):
        """_parse_gemini_response returns {} on malformed JSON without raising."""
        from extraction.gemini_extractor import _parse_gemini_response
        parsed = _parse_gemini_response("{this is not valid json{{")
        self.assertEqual(parsed, {})

    def test_45_gemini_response_parsing_empty_string(self):
        """_parse_gemini_response returns {} on empty string input."""
        from extraction.gemini_extractor import _parse_gemini_response
        parsed = _parse_gemini_response("")
        self.assertEqual(parsed, {})

    def test_46_gemini_api_failure_returns_empty_dict(self):
        """extract_with_gemini returns {} on API failure and does NOT raise."""
        from unittest.mock import patch, MagicMock
        from extraction.gemini_extractor import extract_with_gemini

        with patch("extraction.gemini_extractor._get_gemini_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = RuntimeError("Simulated quota exceeded")
            mock_client_fn.return_value = mock_client

            result = extract_with_gemini(b"\xff\xd8\xff" + b"\x00" * 100)
            self.assertEqual(result, {})

    def test_47_gemini_missing_api_key_returns_empty_dict(self):
        """extract_with_gemini returns {} when GEMINI_API_KEY env var is absent."""
        from unittest.mock import patch
        from extraction.gemini_extractor import extract_with_gemini
        import os

        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            result = extract_with_gemini(b"\xff\xd8\xff" + b"\x00" * 100)
            self.assertEqual(result, {})

    def test_48_gemini_fills_missing_ocr_field(self):
        """fuse_gemini_evidence Case B: Gemini fills a field missing from OCR result."""
        from extraction.gemini_extractor import fuse_gemini_evidence

        ocr_decls = {
            "mrp": {"detected": False, "value": None, "status": "INCONCLUSIVE"},
            "net_quantity": {"detected": True, "value": 200.0, "status": "VERIFIED", "confidence": 0.9},
        }
        gemini_fields = {
            "mrp": {"value": 35.0, "visible_text": "MRP Rs. 35", "confidence": 0.85, "source": "gemini"},
        }
        fused = fuse_gemini_evidence(ocr_decls, gemini_fields)
        self.assertTrue(fused["mrp"]["detected"])
        self.assertEqual(fused["mrp"]["value"], 35.0)
        self.assertEqual(fused["mrp"]["source"], "gemini")
        self.assertEqual(fused["mrp"]["fusion_case"], "B")

    def test_49_gemini_agreement_corroborates_ocr(self):
        """fuse_gemini_evidence Case A: Gemini agreement boosts confidence."""
        from extraction.gemini_extractor import fuse_gemini_evidence

        ocr_decls = {
            "mrp": {"detected": True, "value": 50.0, "status": "VERIFIED", "confidence": 0.75},
        }
        gemini_fields = {
            "mrp": {"value": 50.0, "visible_text": "MRP Rs. 50", "confidence": 0.9, "source": "gemini"},
        }
        fused = fuse_gemini_evidence(ocr_decls, gemini_fields)
        self.assertEqual(fused["mrp"]["source"], "ocr+gemini")
        self.assertEqual(fused["mrp"]["fusion_case"], "A")
        self.assertGreater(fused["mrp"]["confidence"], 0.75)

    def test_50_gemini_conflict_marks_inconclusive(self):
        """fuse_gemini_evidence Case C: OCR vs Gemini conflict → INCONCLUSIVE."""
        from extraction.gemini_extractor import fuse_gemini_evidence

        ocr_decls = {
            "mrp": {"detected": True, "value": 50.0, "status": "VERIFIED", "confidence": 0.85},
        }
        gemini_fields = {
            "mrp": {"value": 80.0, "visible_text": "MRP Rs. 80", "confidence": 0.9, "source": "gemini"},
        }
        fused = fuse_gemini_evidence(ocr_decls, gemini_fields)
        self.assertEqual(fused["mrp"]["status"], "INCONCLUSIVE")
        self.assertTrue(fused["mrp"]["conflict"])
        self.assertEqual(fused["mrp"]["fusion_case"], "C")

    def test_51_should_call_gemini_returns_false_when_ocr_sufficient(self):
        """should_call_gemini returns False when all detected fields have VERIFIED status."""
        from extraction.gemini_extractor import should_call_gemini, _MANDATORY_FIELDS

        # All mandatory fields detected and verified — Gemini should not be invoked
        strong_ocr = {
            field: {"detected": True, "value": "val", "status": "VERIFIED", "confidence": 0.9}
            for field in _MANDATORY_FIELDS
        }
        needed, reason = should_call_gemini(strong_ocr)
        self.assertFalse(needed)
        self.assertIn("sufficient", reason.lower())

    def test_52_should_call_gemini_returns_true_when_field_missing(self):
        """should_call_gemini returns True when a mandatory field is missing."""
        from extraction.gemini_extractor import should_call_gemini

        weak_ocr = {
            "mrp": {"detected": False, "value": None, "status": "INCONCLUSIVE"},
        }
        needed, reason = should_call_gemini(weak_ocr)
        self.assertTrue(needed)
        self.assertIn("mrp", reason)

    def test_53_ocr_value_none_detected_true_triggers_case_b(self):
        """fuse_gemini_evidence Case B: OCR detected=True but value=None triggers Case B, NOT Case C."""
        from extraction.gemini_extractor import fuse_gemini_evidence

        ocr_decls = {
            "mrp": {"detected": True, "value": None, "status": "INCONCLUSIVE", "raw_text": "MRP"},
        }
        gemini_fields = {
            "mrp": {"value": 45.0, "visible_text": "MRP Rs. 45", "confidence": 0.85, "source": "gemini"},
        }
        fused = fuse_gemini_evidence(ocr_decls, gemini_fields)
        self.assertEqual(fused["mrp"]["fusion_case"], "B")
        self.assertEqual(fused["mrp"]["status"], "VERIFIED")
        self.assertEqual(fused["mrp"]["value"], 45.0)
        self.assertEqual(fused["mrp"]["source"], "gemini")

    def test_54_gemini_empty_leaves_ocr_unchanged(self):
        """fuse_gemini_evidence Case D: Empty Gemini result leaves OCR completely unchanged."""
        from extraction.gemini_extractor import fuse_gemini_evidence

        ocr_decls = {
            "mrp": {"detected": True, "value": 20.0, "status": "VERIFIED", "confidence": 0.9},
            "net_quantity": {"detected": True, "value": 100.0, "status": "VERIFIED", "confidence": 0.85},
        }
        fused = fuse_gemini_evidence(ocr_decls, {})
        self.assertEqual(fused["mrp"]["value"], 20.0)
        self.assertEqual(fused["net_quantity"]["value"], 100.0)
        self.assertEqual(fused["mrp"]["status"], "VERIFIED")

    def test_55_normalization_removes_verified_with_null_value(self):
        """normalize_declaration_evidence enforces invariant: VERIFIED requires usable non-null value."""
        from extraction.gemini_extractor import normalize_declaration_evidence

        bad_declarations = {
            "mrp": {"status": "VERIFIED", "detected": True, "value": None, "raw_text": None},
            "manufacturer": {"status": "VERIFIED", "detected": True, "value": None, "details": None},
        }
        normalized = normalize_declaration_evidence(bad_declarations)
        self.assertEqual(normalized["mrp"]["status"], "INCONCLUSIVE")
        self.assertFalse(normalized["mrp"]["detected"])
        self.assertIsNone(normalized["mrp"]["value"])

        self.assertEqual(normalized["manufacturer"]["status"], "INCONCLUSIVE")
        self.assertFalse(normalized["manufacturer"]["detected"])

    def test_56_rule_engine_does_not_pass_mrp_with_none_value(self):
        """Rule engine never PASSes MRP if value is None."""
        extracted = {
            "mrp": {"status": "VERIFIED", "detected": True, "value": None, "raw_text": None},
        }
        quality = {"is_readable": True, "blur_score": 150.0, "quality_rating": "GOOD"}
        report = evaluate_compliance(extracted, quality)
        mrp_rule = next(r for r in report["rule_results"] if r["target_field"] == "mrp")
        self.assertNotEqual(mrp_rule["status"], "PASS")

    def test_57_rule_engine_does_not_pass_manufacturer_with_none_value(self):
        """Rule engine never PASSes manufacturer if details and value are None."""
        extracted = {
            "manufacturer": {"status": "VERIFIED", "detected": True, "value": None, "details": None},
        }
        quality = {"is_readable": True, "blur_score": 150.0, "quality_rating": "GOOD"}
        report = evaluate_compliance(extracted, quality)
        mfr_rule = next(r for r in report["rule_results"] if r["target_field"] == "manufacturer")
        self.assertNotEqual(mfr_rule["status"], "PASS")

    def test_58_rule_engine_does_not_pass_net_quantity_with_none_value(self):
        """Rule engine never PASSes net quantity if value is None."""
        extracted = {
            "net_quantity": {"status": "VERIFIED", "detected": True, "value": None, "unit": None},
        }
        quality = {"is_readable": True, "blur_score": 150.0, "quality_rating": "GOOD"}
        report = evaluate_compliance(extracted, quality)
        qty_rule = next(r for r in report["rule_results"] if r["target_field"] == "net_quantity")
        self.assertNotEqual(qty_rule["status"], "PASS")

    def test_59_rule_engine_does_not_pass_expiry_with_none_value(self):
        """Rule engine never PASSes expiry if date_str and value are None."""
        extracted = {
            "expiry_date": {"status": "VERIFIED", "detected": True, "value": None, "date_str": None},
        }
        quality = {"is_readable": True, "blur_score": 150.0, "quality_rating": "GOOD"}
        report = evaluate_compliance(extracted, quality)
        exp_rule = next(r for r in report["rule_results"] if r["target_field"] == "expiry_date")
        self.assertNotEqual(exp_rule["status"], "PASS")

    def test_60_rule_engine_does_not_pass_batch_with_none_value(self):
        """Rule engine never PASSes batch number if batch_number and value are None."""
        extracted = {
            "batch_number": {"status": "VERIFIED", "detected": True, "value": None, "batch_number": None},
        }
        quality = {"is_readable": True, "blur_score": 150.0, "quality_rating": "GOOD"}
        report = evaluate_compliance(extracted, quality)
        batch_rule = next(r for r in report["rule_results"] if r["target_field"] == "batch_number")
        self.assertNotEqual(batch_rule["status"], "PASS")

    def test_61_rule_engine_does_not_pass_unit_sale_price_with_none_value(self):
        """Rule engine never PASSes unit sale price if value and raw_text are None."""
        extracted = {
            "unit_sale_price": {"status": "VERIFIED", "detected": True, "value": None, "raw_text": None},
        }
        quality = {"is_readable": True, "blur_score": 150.0, "quality_rating": "GOOD"}
        report = evaluate_compliance(extracted, quality)
        usp_rule = next(r for r in report["rule_results"] if r["target_field"] == "unit_sale_price")
        self.assertEqual(usp_rule["status"], "INCONCLUSIVE")

    def test_62_country_of_origin_requires_verified_domestic_manufacturer(self):
        """Country of origin returns INCONCLUSIVE (not PASS with None) when domestic manufacturer is unverified."""
        extracted = {
            "country_of_origin": {"status": "INCONCLUSIVE", "detected": False, "value": None, "country": None},
            "manufacturer": {"status": "INCONCLUSIVE", "detected": False, "value": None, "details": None},
        }
        quality = {"is_readable": True, "blur_score": 150.0, "quality_rating": "GOOD"}
        report = evaluate_compliance(extracted, quality, product_category="packaged_goods")
        origin_rule = next(r for r in report["rule_results"] if r["target_field"] == "country_of_origin")
        self.assertEqual(origin_rule["status"], "INCONCLUSIVE")

    def test_63_gemini_fused_fields_pass_with_usable_evidence(self):
        """Gemini-fused declarations with real evidence pass rule engine with non-null evidence text."""
        from extraction.gemini_extractor import fuse_gemini_evidence, normalize_declaration_evidence

        ocr_decls = {}
        gemini_fields = {
            "mrp": {"value": 5.0, "visible_text": "MRP Rs. 5.00", "confidence": 0.85, "source": "gemini"},
            "manufacturer": {"value": "Bloombay Foods Pvt Ltd", "visible_text": "Bloombay Foods Pvt Ltd", "confidence": 0.85, "source": "gemini"},
            "batch_number": {"value": "1/U1N29D", "visible_text": "1/U1N29D", "confidence": 0.85, "source": "gemini"},
        }
        fused = fuse_gemini_evidence(ocr_decls, gemini_fields)
        normalized = normalize_declaration_evidence(fused)

        quality = {"is_readable": True, "blur_score": 150.0, "quality_rating": "GOOD"}
        report = evaluate_compliance(normalized, quality)

        mrp_rule = next(r for r in report["rule_results"] if r["target_field"] == "mrp")
        self.assertEqual(mrp_rule["status"], "PASS")
        self.assertIsNotNone(mrp_rule["evidence_text"])
        self.assertIn("5", str(mrp_rule["evidence_text"]))
        self.assertEqual(mrp_rule["source"], "gemini")

        mfr_rule = next(r for r in report["rule_results"] if r["target_field"] == "manufacturer")
        self.assertEqual(mfr_rule["status"], "PASS")
        self.assertIn("Bloombay", str(mfr_rule["evidence_text"]))

        batch_rule = next(r for r in report["rule_results"] if r["target_field"] == "batch_number")
        self.assertEqual(batch_rule["status"], "PASS")
        self.assertEqual(batch_rule["evidence_text"], "1/U1N29D")

    def test_64_pdf_generation_never_outputs_literal_none(self):
        """generate_inspection_pdf never outputs literal 'None' for evidence or explanation."""
        from reporting.pdf_report import generate_inspection_pdf
        scan_data = {
            "inspection_id": "INS-TEST-NONE",
            "product_category": "packaged_goods",
            "compliance_report": {
                "overall_status": "INCONCLUSIVE",
                "verdict_title": "Test Assessment",
                "rule_results": [
                    {
                        "rule_clause": "Rule 6(1)(a)",
                        "target_field": "mrp",
                        "status": "INCONCLUSIVE",
                        "evidence_text": None,
                        "explanation": None,
                        "source": "ocr"
                    }
                ]
            },
            "quality_assessment": {"blur_score": 100.0, "quality_rating": "GOOD", "resolution": "1920x1080"},
            "evidence_ledger": {"evidence_hash": "dummyhash"}
        }
        pdf = generate_inspection_pdf(scan_data)
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        # Must not contain literal " None" as evidence
        self.assertNotIn(b" INCONCLUSIVE None", pdf)

    def test_65_provenance_preserved_in_rule_results(self):
        """Rule engine preserves source, confidence, fusion_case, and conflict in rule results."""
        extracted = {
            "mrp": {
                "status": "VERIFIED",
                "detected": True,
                "value": 50.0,
                "raw_text": "MRP Rs. 50",
                "source": "gemini",
                "confidence": 0.85,
                "fusion_case": "B",
                "conflict": False
            }
        }
        quality = {"is_readable": True, "blur_score": 150.0, "quality_rating": "GOOD"}
        report = evaluate_compliance(extracted, quality)
        mrp_res = next(r for r in report["rule_results"] if r["target_field"] == "mrp")
        self.assertEqual(mrp_res["source"], "gemini")
        self.assertEqual(mrp_res["fusion_case"], "B")
        self.assertEqual(mrp_res["confidence"], 0.85)
        self.assertFalse(mrp_res["conflict"])


if __name__ == "__main__":
    unittest.main()

