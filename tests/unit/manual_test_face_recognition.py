#!/usr/bin/env python3
"""
Manual Unit Test: Apple Vision Face Recognition.

Verifies:
1. Camera access (built-in FaceTime HD).
2. Face detection via VNDetectFaceRectanglesRequest.
3. Landmark extraction via VNDetectFaceLandmarksRequest.
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_face_recognition(camera_index: Optional[int] = None):
    """Quick test: can Vision Framework detect a face?"""
    print("\n--- Testing Vision Framework Face Detection ---")

    try:
        from Vision import VNDetectFaceRectanglesRequest
        print("✅ Vision Framework accessible")
    except ImportError:
        print("❌ Vision Framework not available")
        print("   Install: pip install pyobjc-framework-Vision")
        return False

    try:
        from src.modules.vision.face_recognizer import VisionFaceRecognizer
        import cv2
        
        idx = camera_index if camera_index is not None else VisionFaceRecognizer.get_default_camera_index()
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            print(f"❌ Cannot open camera {idx}")
            return False

        ret, frame = cap.read()
        cap.release()

        if not ret:
            print("❌ Cannot capture frame")
            return False

        print("✅ Camera capture working")

        rec = VisionFaceRecognizer(boss_encodings_path="data/faces/boss_vision.pkl")

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        landmarks = rec._extract_landmarks_vision(rgb)

        if landmarks is not None:
            print(f"✅ Face detected! Landmark points: {len(landmarks)}")
            return True
        else:
            print("⚠️  No face detected in test frame (try again with face visible)")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Face Recognition Unit Test")
    parser.add_argument("--camera", type=int, default=None, help="Camera index")
    args = parser.parse_args()
    
    success = test_face_recognition(camera_index=args.camera)
    sys.exit(0 if success else 1)
