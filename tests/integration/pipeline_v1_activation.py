import os
import sys
import time
import logging

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.activation_handler import ActivationHandler, ActivationState

# Configure logging to see what is happening
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logging.getLogger("friday.wake_word").setLevel(logging.DEBUG)

logger = logging.getLogger("test_pipeline")

def say(text):
    """Fallback text-to-speech using macOS native 'say' command."""
    os.system(f'say "{text}"')

def on_boss_verified():
    logger.info("CALLBACK: Boss has been verified!")
    # We no longer need to manually transition states here,
    # and we removed the duplicate 'say' call because the handler
    # or the VoicePipeline will take over.
    
def on_stranger():
    logger.info("CALLBACK: Stranger detected.")

def on_no_face():
    logger.info("CALLBACK: No face detected.")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("F.R.I.D.A.Y. Pipeline Integration Test (Fixed)")
    print("Wake Word -> Vision Recognition -> Voice Loop")
    print("=" * 60)
    print("\nSay 'Hey Mycroft' to trigger the pipeline.")
    print("Ensure you are visible to the camera when triggering.")
    print("Press Ctrl+C to stop.\n")

    boss_encodings = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "faces", "boss_vision.pkl")
    
    if not os.path.exists(boss_encodings):
        logger.error(f"Could not find boss encodings at {boss_encodings}")
        logger.error("Please run 'make enroll-face' first!")
        sys.exit(1)

    import argparse
    parser = argparse.ArgumentParser(description="F.R.I.D.A.Y. Pipeline Test")
    parser.add_argument("--camera", type=int, default=None, help="Camera device index")
    args = parser.parse_args()

    handler = ActivationHandler(
        boss_encodings_path=boss_encodings,
        on_boss_verified=on_boss_verified,
        on_stranger=on_stranger,
        on_no_face=on_no_face,
        camera_index=args.camera
    )

    try:
        handler.start()
        # This will now block and process camera/brain on the main thread!
        handler.run_loop()
        
    except KeyboardInterrupt:
        print("\nStopping pipeline test...")
        handler.stop()
        print("Done.")
