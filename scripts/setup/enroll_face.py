#!/usr/bin/env python3
"""
Face enrollment using Apple Vision Framework.

Captures 20-30 photos with varied angles and lighting for
robust 1-to-1 face verification.

Usage:
    python scripts/enroll_face_vision.py
    python scripts/enroll_face_vision.py --photos 30
    python scripts/enroll_face_vision.py --test  # Quick verification test
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def enroll():
    """Full enrollment flow."""
    print("\n" + "=" * 60)
    print("F.R.I.D.A.Y. FACE ENROLLMENT — Apple Vision Framework")
    print("=" * 60)
    print("\nThis will capture face photos for identity verification.")
    print("\n📸 Guidance for best results:")
    print("   • Good lighting (face the window or desk lamp)")
    print("   • Vary angle: straight, 15° left, 15° right")
    print("   • Try with/without glasses (if applicable)")
    print("   • Different expressions: neutral, slight smile")
    print("\n   Press SPACE to capture each photo")
    print("   Press ESC to cancel")

    input("\nPress ENTER to start...")

    from src.modules.vision.face_recognizer import VisionFaceRecognizer

    save_path = PROJECT_ROOT / "data" / "faces" / "boss_vision.pkl"
    rec = VisionFaceRecognizer(boss_encodings_path=str(save_path))

    success = rec.enroll_boss(
        num_photos=args.photos,
        save_path=str(save_path),
        camera_index=args.camera,
    )

    if success:
        print("\n✅ Enrollment complete!")
        print(f"   Saved to: {save_path}")
        print(f"   File size: {save_path.stat().st_size / 1024:.1f} KB")

        # Quick verification test
        print("\n--- Quick Verification Test ---")
        print("Look at the camera...")
        time.sleep(1)

        identity, name = rec.verify_identity(camera_index=args.camera)
        print(f"Result: {identity} ({name})")

        if identity == "boss":
            print("✅ Successfully recognized as Boss!")
        else:
            print("⚠️  Not recognized — enrollment quality may need improvement")
            print("   Try: python scripts/setup/enroll_face.py --photos 30")
    else:
        print("\n❌ Enrollment failed")
        return 1

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FRIDAY face enrollment")
    parser.add_argument(
        "--photos", type=int, default=20,
        help="Number of photos to capture (default: 20)",
    )
    parser.add_argument(
        "--camera", type=int, default=None,
        help="Camera device index (default: auto-detect FaceTime HD Camera)",
    )
    args = parser.parse_args()

    sys.exit(enroll())
