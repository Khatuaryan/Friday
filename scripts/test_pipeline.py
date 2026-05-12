import os
import sys
import time
import logging

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    os.system(f"say '{text}'")

def on_boss_verified():
    logger.info("CALLBACK: Boss has been verified!")
    say("Hey Boss, what can I do for you?")
    
    # Normally we would transition to listening for a voice command here
    # For this test, we'll just wait a bit and go back to idle listening
    time.sleep(2)
    handler._set_state(ActivationState.LISTENING) # Reset state for the test loop
    logger.info("System reset. Listening for wake word again...")

def on_stranger():
    logger.info("CALLBACK: Stranger detected.")
    say("I'm sorry, I am only authorized to assist Boss.")

def on_no_face():
    logger.info("CALLBACK: No face detected.")
    say("I heard you, but I couldn't see your face.")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("F.R.I.D.A.Y. Pipeline Integration Test")
    print("Wake Word -> Vision Recognition -> Text To Speech")
    print("=" * 60)
    print("\nSay 'Hey Mycroft' to trigger the pipeline.")
    print("Ensure you are visible to the camera when triggering.")
    print("Press Ctrl+C to stop.\n")

    boss_encodings = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "faces", "boss_vision.pkl")
    
    if not os.path.exists(boss_encodings):
        logger.error(f"Could not find boss encodings at {boss_encodings}")
        logger.error("Please run 'make enroll-face' first!")
        sys.exit(1)

    handler = ActivationHandler(
        boss_encodings_path=boss_encodings,
        on_boss_verified=on_boss_verified,
        on_stranger=on_stranger,
        on_no_face=on_no_face
    )

    try:
        handler.start()
        
        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping pipeline test...")
        handler.stop()
        print("Done.")
