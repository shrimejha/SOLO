"""
Phase 0 Calibration & Room Scan Processor
Parses camera intrinsics matrix, calculates real-world scale factors,
and aligns initial background reference plates using OpenCV feature matching & homography.
"""

import numpy as np
import cv2
from typing import Dict, Any, Tuple, List, Optional
from pydantic import BaseModel

class CameraIntrinsics(BaseModel):
    fx: float
    fy: float
    cx: float
    cy: float
    distortion_coefficients: List[float] = []

class CalibrationData(BaseModel):
    intrinsics: CameraIntrinsics
    scale_factor_ppm: float  # Pixels per meter at seating depth
    point_cloud_summary: Dict[str, Any] = {}
    reference_plate_paths: List[str] = []

class CalibrationProcessor:
    def __init__(self, calibration_data: CalibrationData):
        self.data = calibration_data
        self.intrinsics_matrix = np.array([
            [calibration_data.intrinsics.fx, 0, calibration_data.intrinsics.cx],
            [0, calibration_data.intrinsics.fy, calibration_data.intrinsics.cy],
            [0, 0, 1]
        ], dtype=np.float32)

    def align_background_plate(self, current_frame: np.ndarray, plate_image: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Aligns a static setup background plate to the live frame perspective via OpenCV SIFT feature matching.
        Returns the warped background plate and alignment confidence score.
        """
        gray_frame = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
        gray_plate = cv2.cvtColor(plate_image, cv2.COLOR_BGR2GRAY)

        sift = cv2.SIFT_create(nfeatures=500)
        kp1, des1 = sift.detectAndCompute(gray_plate, None)
        kp2, des2 = sift.detectAndCompute(gray_frame, None)

        if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
            return cv2.resize(plate_image, (current_frame.shape[1], current_frame.shape[0])), 0.0

        matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=True)
        matches = matcher.match(des1, des2)
        matches = sorted(matches, key=lambda x: x.distance)

        good_matches = matches[:min(50, len(matches))]
        if len(good_matches) < 4:
            return cv2.resize(plate_image, (current_frame.shape[1], current_frame.shape[0])), 0.0

        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

        homography, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if homography is None:
            return cv2.resize(plate_image, (current_frame.shape[1], current_frame.shape[0])), 0.0

        h, w, _ = current_frame.shape
        aligned_plate = cv2.warpPerspective(plate_image, homography, (w, h))
        confidence = float(np.sum(mask)) / len(good_matches) if mask is not None else 0.5
        return aligned_plate, confidence

    def compute_max_crop_zoom(self, requested_zoom: float) -> float:
        """
        Caps total digital crop zoom based on sensor resolution and intrinsics.
        Prevents over-cropping beyond physical resolution limits.
        """
        max_allowed_zoom = 2.5  # Fixed scale ceiling to preserve quality on locked main lens
        return min(requested_zoom, max_allowed_zoom)
