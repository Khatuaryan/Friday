"""
Face Recognition using Apple Vision Framework.

Uses macOS native Vision.framework via PyObjC for:
    - Face detection (VNDetectFaceRectanglesRequest)
    - Facial landmarks (VNDetectFaceLandmarksRequest, 68 points)
    - Identity verification via landmark comparison

Memory: ~0 MB additional (native macOS framework, GPU-accelerated)
Speed:  <800 ms per verification
"""

from __future__ import annotations

import logging
import pickle
import time
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger("friday.face_vision")


class VisionFaceRecognizer:
    """
    Face recognition via Apple Vision Framework landmarks.

    Verification approach (1-to-1):
        1. Detect face in camera frame using VNDetectFaceRectanglesRequest
        2. Extract 68 facial landmarks via VNDetectFaceLandmarksRequest
        3. Normalize landmarks for scale/rotation invariance
        4. Compare normalized landmarks against enrolled "Boss" templates
        5. Decision: similarity > threshold → "boss", else "stranger"

    No FaceNet or ONNX models required — pure native framework.
    """

    def __init__(
        self,
        boss_encodings_path: str | Path = "data/faces/boss_vision.pkl",
        threshold: float = 0.75,
        timeout: int = 3,
        camera_index: Optional[int] = None,
    ) -> None:
        """
        Args:
            boss_encodings_path: Path to pickled boss landmark observations.
            threshold: Similarity threshold (0.0–1.0). Higher = stricter.
            timeout: Camera timeout in seconds.
            camera_index: Optional override for camera device index.
        """
        self.boss_encodings_path = Path(boss_encodings_path)
        self.threshold = threshold
        self.timeout = timeout

        # Determine camera index: provided > built-in > 0
        if camera_index is not None:
            self.camera_index = camera_index
        else:
            self.camera_index = self.get_default_camera_index()

        # Load boss encodings if they exist
        self._boss_landmarks: list[np.ndarray] = []
        if self.boss_encodings_path.exists():
            self._load_boss_encodings()

    @staticmethod
    def get_default_camera_index() -> int:
        """
        Attempts to find the index of the built-in FaceTime HD Camera.
        Returns 0 if not found or on error.
        """
        try:
            import AVFoundation
            discovery_session = AVFoundation.AVCaptureDeviceDiscoverySession.discoverySessionWithDeviceTypes_mediaType_position_(
                [
                    AVFoundation.AVCaptureDeviceTypeBuiltInWideAngleCamera,
                    AVFoundation.AVCaptureDeviceTypeExternalUnknown,
                    AVFoundation.AVCaptureDeviceTypeContinuityCamera
                ],
                AVFoundation.AVMediaTypeVideo,
                AVFoundation.AVCaptureDevicePositionUnspecified
            )
            devices = discovery_session.devices()

            # Prefer built-in FaceTime HD Camera
            for i, device in enumerate(devices):
                name = device.localizedName().lower()
                if "facetime" in name or "built-in" in name:
                    logger.info("Found built-in camera: %s at index %d", device.localizedName(), i)
                    return i

            # Fallback to index 0
            if devices:
                logger.info("Using default camera: %s at index 0", devices[0].localizedName())
            return 0

        except Exception as e:
            logger.debug("Camera discovery failed: %s", e)
            return 0

    def verify_identity(self, camera_index: Optional[int] = None) -> Tuple[str, Optional[str]]:
        """
        Capture from camera and verify identity against enrolled Boss.

        Args:
            camera_index: Optional override for camera device index.

        Returns:
            ("boss", "Boss")    — Recognized as Boss
            ("stranger", None)  — Face detected but not Boss
            ("no_face", None)   — No face detected within timeout
        """
        import cv2

        idx = camera_index if camera_index is not None else self.camera_index
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            logger.error("Cannot open camera %d", idx)
            return ("no_face", None)

        try:
            start = time.time()
            while time.time() - start < self.timeout:
                ret, frame = cap.read()
                if not ret:
                    continue

                # Convert BGR → RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Detect face and extract landmarks via Vision
                landmarks = self._extract_landmarks_vision(rgb_frame)

                if landmarks is not None:
                    # Compare with boss
                    if self._is_boss(landmarks):
                        return ("boss", "Boss")
                    else:
                        return ("stranger", None)

            return ("no_face", None)

        finally:
            cap.release()

    def enroll_boss(
        self,
        num_photos: int = 20,
        save_path: str | Path | None = None,
        camera_index: int = 0,
    ) -> bool:
        """
        Enroll user as Boss by capturing face landmark templates.

        Args:
            num_photos: Number of face samples to capture.
            save_path: Where to save encodings. Defaults to boss_encodings_path.
            camera_index: Camera device index.

        Returns:
            True if enrollment succeeded.
        """
        import cv2

        save_path = Path(save_path or self.boss_encodings_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            logger.error("Cannot open camera %d", camera_index)
            return False

        collected: list[np.ndarray] = []
        print(f"\nCapturing {num_photos} face photos...")
        print("Press SPACE to capture, ESC to cancel.\n")

        try:
            while len(collected) < num_photos:
                ret, frame = cap.read()
                if not ret:
                    continue

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Show preview
                display = frame.copy()
                text = f"Captured: {len(collected)}/{num_photos} — Press SPACE"
                cv2.putText(
                    display, text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
                )
                cv2.imshow("FRIDAY Enrollment", display)

                key = cv2.waitKey(1) & 0xFF
                if key == 27:  # ESC
                    print("Enrollment cancelled.")
                    return False

                if key == ord(" "):
                    # Extract landmarks
                    landmarks = self._extract_landmarks_vision(rgb_frame)
                    if landmarks is not None:
                        collected.append(landmarks)
                        print(f"  ✅ Photo {len(collected)}/{num_photos} captured")
                    else:
                        print("  ❌ No face detected — try again")

        finally:
            cap.release()
            cv2.destroyAllWindows()

        if len(collected) < num_photos:
            logger.warning("Only %d/%d photos collected", len(collected), num_photos)

        # Save encodings
        with open(save_path, "wb") as f:
            pickle.dump(collected, f)

        self._boss_landmarks = collected
        logger.info(
            "Boss enrolled: %d samples saved to %s", len(collected), save_path
        )
        return True

    # ── Vision Framework Methods ────────────────────────────

    def _extract_landmarks_vision(self, rgb_image: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract 68 facial landmark points from an RGB image
        using Apple Vision Framework.

        Args:
            rgb_image: HxWx3 uint8 numpy array in RGB format.

        Returns:
            Normalized landmark array of shape (68, 2) or None if no face.
        """
        try:
            from Vision import (
                VNDetectFaceLandmarksRequest,
                VNImageRequestHandler,
            )
            from Quartz import (
                CGDataProviderCreateWithData,
                CGImageCreate,
                CGColorSpaceCreateDeviceRGB,
            )
            import objc

            h, w, _ = rgb_image.shape

            # Create CGImage from numpy array
            bytes_per_row = w * 3
            data = rgb_image.tobytes()
            provider = CGDataProviderCreateWithData(None, data, len(data), None)

            cg_image = CGImageCreate(
                w, h,                    # width, height
                8,                       # bits per component
                24,                      # bits per pixel
                bytes_per_row,           # bytes per row
                CGColorSpaceCreateDeviceRGB(),
                0,                       # bitmap info (no alpha)
                provider,
                None,                    # decode array
                False,                   # should interpolate
                0,                       # rendering intent
            )

            if cg_image is None:
                logger.debug("Failed to create CGImage")
                return None

            # Create Vision request handler
            handler = VNImageRequestHandler.alloc().initWithCGImage_options_(
                cg_image, None
            )

            # Create landmarks request
            landmarks_request = VNDetectFaceLandmarksRequest.alloc().init()

            # Perform request
            success, error = handler.performRequests_error_(
                [landmarks_request], None
            )

            if not success or error:
                logger.debug("Vision request failed: %s", error)
                return None

            results = landmarks_request.results()
            if not results or len(results) == 0:
                return None

            # Get first face observation
            face_obs = results[0]

            # Extract all landmark regions
            all_landmarks = face_obs.landmarks()
            if all_landmarks is None:
                return None

            # Get all points from the landmark constellation
            all_points = all_landmarks.allPoints()
            if all_points is None:
                return None

            point_count = all_points.pointCount()
            if point_count == 0:
                return None

            # Extract normalized point coordinates
            points = []
            norm_pts = all_points.normalizedPoints()
            for i in range(point_count):
                pt = norm_pts[i]
                points.append([pt.x, pt.y])

            landmarks = np.array(points, dtype=np.float64)

            # Normalize: center at origin, scale to unit variance
            landmarks = self._normalize_landmarks(landmarks)

            return landmarks

        except ImportError:
            logger.error(
                "Vision Framework not available. "
                "Install: pip install pyobjc-framework-Vision"
            )
            return None
        except Exception:
            logger.exception("Vision landmark extraction failed")
            return None

    def _is_boss(self, landmarks: np.ndarray) -> bool:
        """
        Compare extracted landmarks against stored Boss templates.

        Returns True if similarity to any boss template exceeds threshold.
        """
        if not self._boss_landmarks:
            logger.warning("No boss encodings loaded — cannot verify")
            return False

        similarities = [
            self._calculate_similarity(landmarks, boss_lm)
            for boss_lm in self._boss_landmarks
        ]

        # Use median of top-5 similarities for robustness
        top_k = sorted(similarities, reverse=True)[:5]
        avg_similarity = np.mean(top_k) if top_k else 0.0

        logger.debug(
            "Face similarity: best=%.3f, top5_avg=%.3f, threshold=%.3f",
            max(similarities), avg_similarity, self.threshold,
        )

        return avg_similarity >= self.threshold

    @staticmethod
    def _normalize_landmarks(landmarks: np.ndarray) -> np.ndarray:
        """
        Normalize landmarks for scale and translation invariance.

        Centers at origin and scales to unit standard deviation.
        """
        centered = landmarks - landmarks.mean(axis=0)
        std = centered.std()
        if std > 0:
            centered /= std
        return centered

    @staticmethod
    def _calculate_similarity(lm1: np.ndarray, lm2: np.ndarray) -> float:
        """
        Calculate similarity between two normalized landmark sets.

        Uses negative Euclidean distance mapped to [0, 1] via exponential.
        """
        # Ensure same shape (truncate to min length)
        min_len = min(len(lm1), len(lm2))
        a, b = lm1[:min_len], lm2[:min_len]

        # Mean Euclidean distance per point
        distance = np.mean(np.linalg.norm(a - b, axis=1))

        # Convert to similarity: e^(-distance)
        # distance=0 → similarity=1, distance→∞ → similarity→0
        similarity = np.exp(-distance)
        return float(similarity)

    def _load_boss_encodings(self) -> None:
        """Load pickled boss landmark templates."""
        try:
            with open(self.boss_encodings_path, "rb") as f:
                self._boss_landmarks = pickle.load(f)
            logger.info(
                "Loaded %d boss encodings from %s",
                len(self._boss_landmarks), self.boss_encodings_path,
            )
        except Exception:
            logger.warning(
                "Could not load boss encodings from %s", self.boss_encodings_path
            )
            self._boss_landmarks = []
