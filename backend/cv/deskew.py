"""
OpenCV Image Deskewing & Perspective Distortion Correction Module
-------------------------------------------------------------------
Detects text line tilt angles, corrects perspective distortions on packaging,
and auto-aligns label photographs horizontally before OCR processing.
"""

import math
from typing import Tuple, Optional
import numpy as np

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


def detect_text_skew_angle(image_bgr: np.ndarray) -> float:
    """
    Detects principal text line skew angle (-45 to +45 degrees) using OpenCV contour minAreaRect.
    """
    if not OPENCV_AVAILABLE or image_bgr is None:
        return 0.0

    try:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if len(image_bgr.shape) == 3 else image_bgr
        
        # Otsu thresholding + Inversion
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Dilate text regions horizontally to form line blocks
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
        dilated = cv2.dilate(thresh, kernel, iterations=2)

        # Find contours of text line blocks
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        angles = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < 500:  # Ignore small noise contours
                continue
            
            rect = cv2.minAreaRect(c)
            angle = rect[-1]

            # Adjust OpenCV minAreaRect angle ranges
            if angle < -45:
                angle = 90 + angle
            elif angle > 45:
                angle = angle - 90
            
            if abs(angle) > 0.5:
                angles.append(angle)

        if not angles:
            return 0.0

        # Return median skew angle
        median_angle = float(np.median(angles))
        return median_angle if abs(median_angle) <= 45.0 else 0.0

    except Exception:
        return 0.0


def deskew_image(image_bgr: np.ndarray, angle: Optional[float] = None) -> np.ndarray:
    """
    Rotates an image by the detected skew angle to align text horizontally.
    """
    if not OPENCV_AVAILABLE or image_bgr is None:
        return image_bgr

    try:
        if angle is None:
            angle = detect_text_skew_angle(image_bgr)

        if abs(angle) < 0.8:  # Negligible tilt, no rotation needed
            return image_bgr

        h, w = image_bgr.shape[:2]
        center = (w // 2, h // 2)

        # Compute rotation matrix
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # Compute new bounding dimensions to prevent image clipping
        cos = abs(M[0, 0])
        sin = abs(M[0, 1])
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))

        M[0, 2] += (new_w / 2) - center[0]
        M[1, 2] += (new_h / 2) - center[1]

        rotated = cv2.warpAffine(
            image_bgr, M, (new_w, new_h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255)
        )
        return rotated
    except Exception:
        return image_bgr


def rotate_image_angle(image_bgr: np.ndarray, degrees: int) -> np.ndarray:
    """
    Rotates image by fixed 90, 180, or 270 degrees.
    """
    if not OPENCV_AVAILABLE or image_bgr is None or degrees not in [90, 180, 270]:
        return image_bgr

    try:
        if degrees == 90:
            return cv2.rotate(image_bgr, cv2.ROTATE_90_CLOCKWISE)
        elif degrees == 180:
            return cv2.rotate(image_bgr, cv2.ROTATE_180)
        elif degrees == 270:
            return cv2.rotate(image_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
    except Exception:
        return image_bgr
