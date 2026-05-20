import logging
import threading
import time
import queue
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger("friday.activation")

class ActivationState(str, Enum):
    """Activation pipeline states."""
    IDLE = "idle"
    LISTENING = "listening"        # Wake word active
    VERIFYING = "verifying"        # Face check in progress
    READY = "ready"                # Boss verified, awaiting command
    PROCESSING = "processing"      # Voice pipeline active
    SPEAKING = "speaking"          # TTS playing

class ActivationHandler:
    """
    Coordinates the activation flow:
        Wake word → Face verification → Voice interaction
    """

    def __init__(
        self,
        boss_encodings_path: str,
        on_boss_verified: Callable[[], None],
        on_stranger: Optional[Callable[[], None]] = None,
        on_no_face: Optional[Callable[[], None]] = None,
        camera_index: Optional[int] = None,
    ) -> None:
        self.boss_encodings_path = boss_encodings_path
        self.on_boss_verified = on_boss_verified
        self.on_stranger = on_stranger
        self.on_no_face = on_no_face
        self.camera_index = camera_index

        self._state = ActivationState.IDLE
        self._lock = threading.Lock()
        self._event_queue = queue.Queue()
        self._running = False

        # Components
        self._wake_word = None
        self._face_recognizer = None
        self._stt = None
        self._tts = None
        self._voice_pipeline = None

    @property
    def state(self) -> ActivationState:
        return self._state

    def start(self) -> None:
        """Initialize components and start wake word detector."""
        from src.memory.manager import memory_manager
        memory_manager.log_usage()

        # Initialize wake word detector
        from src.modules.audio.wake_word import WakeWordDetector
        self._wake_word = WakeWordDetector(callback=self._queue_wake_word)

        # Initialize face recognizer
        from src.modules.vision.face_recognizer import VisionFaceRecognizer
        self._face_recognizer = VisionFaceRecognizer(
            boss_encodings_path=self.boss_encodings_path,
            camera_index=self.camera_index,
        )

        # Initialize voice pipeline
        from src.modules.audio.stt import SpeechToText
        from src.modules.audio.tts import TextToSpeech
        from src.modules.voice_pipeline import VoicePipeline

        self._stt = SpeechToText()
        self._tts = TextToSpeech()

        brain = None
        try:
            from src.core.brain import FridayBrain
            brain = FridayBrain()
            brain.load_model()
            logger.info("Brain loaded — full voice interaction ready")
        except Exception as e:
            logger.warning("Brain not available: %s", e)

        self._voice_pipeline = VoicePipeline(stt=self._stt, tts=self._tts, brain=brain)
        
        # Inject voice_pipeline and activation_handler into proactive engine
        # so it can speak reminders AND check pipeline state before doing so
        if brain and getattr(brain, "proactive_engine", None):
            brain.proactive_engine.voice_pipeline = self._voice_pipeline
            brain.proactive_engine.activation_handler = self
        
        self._running = True
        self._wake_word.start()
        self._set_state(ActivationState.LISTENING)
        logger.info("Activation handler started — listening for wake word")

    def run_loop(self) -> None:
        """
        Main execution loop. MUST BE CALLED FROM THE MAIN THREAD.
        Processes events like wake word detections and runs camera/brain logic.
        """
        logger.debug("Main loop started")
        try:
            while self._running:
                try:
                    # Non-blocking check for events
                    event = self._event_queue.get(timeout=0.1)
                    if event == "wake_word":
                        self._handle_activation()
                except queue.Empty:
                    continue
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Stop all activation components."""
        self._running = False
        if self._wake_word:
            self._wake_word.stop()
        if self._tts:
            self._tts.stop()
        self._set_state(ActivationState.IDLE)
        logger.info("Activation handler stopped")

    def _queue_wake_word(self) -> None:
        """Internal callback from detector thread — just queues the event."""
        # Preempt active interaction immediately if the wake word triggers during speech or processing
        if (
            self._state in (ActivationState.SPEAKING, ActivationState.PROCESSING)
            and self._tts
        ):
            logger.info("Wake word detected during active interaction. Preempting immediately!")
            self._tts.stop()

        self._event_queue.put("wake_word")

    def _handle_activation(self) -> None:
        """Runs the verification and interaction (Executed on Main Thread)."""
        with self._lock:
            if self._state != ActivationState.LISTENING:
                return
            self._set_state(ActivationState.VERIFYING)

        logger.info("🎤 Wake word detected! Verifying identity...")

        # Preempt any proactive TTS that may be playing right now.
        # This kills the active `say` subprocess and drains the queue,
        # ensuring the activation pipeline owns the audio output exclusively.
        if self._tts and self._tts.is_speaking:
            logger.info("Preempting proactive TTS for wake word activation")
            self._tts.stop()
        
        # Show a notification for visual feedback
        self._show_notification("F.R.I.D.A.Y.", "Wake word detected. Verifying identity...")
        
        start = time.perf_counter()
        try:
            identity, name = self._face_recognizer.verify_identity(
                camera_index=self.camera_index
            )
            latency = time.perf_counter() - start

            if identity == "boss":
                logger.info("✅ Boss verified in %.2fs", latency)
                self._set_state(ActivationState.READY)
                self._show_notification("F.R.I.D.A.Y.", "Identity verified. Listening...")
                
                # Fire user callback (in thread to avoid blocking main loop if user is slow)
                threading.Thread(target=self.on_boss_verified, daemon=True).start()

                # Start voice interaction
                self._handle_voice_interaction()

            elif identity == "stranger":
                logger.warning("⛔ Stranger detected (%.2fs)", latency)
                if self.on_stranger:
                    self.on_stranger()
                self._set_state(ActivationState.LISTENING)

            else:  # no_face
                logger.info("❌ No face detected (%.2fs)", latency)
                if self.on_no_face:
                    self.on_no_face()
                self._set_state(ActivationState.LISTENING)

        except Exception:
            logger.exception("Face verification failed")
            self._set_state(ActivationState.LISTENING)

    def _handle_voice_interaction(self) -> None:
        """Run the voice pipeline (Executed on Main Thread)."""
        if not self._voice_pipeline:
            self._set_state(ActivationState.LISTENING)
            return

        try:
            if self._tts:
                self._tts.reset_preempt()
            self._set_state(ActivationState.SPEAKING)
            self._tts.speak("Hey Boss, how can I help?", blocking=True)

            self._set_state(ActivationState.PROCESSING)
            response = self._voice_pipeline.process_voice_command(timeout=10)

            if response:
                logger.info("Voice command completed successfully")
            else:
                self._tts.speak("I didn't hear anything.", blocking=True)

        except Exception:
            logger.exception("Voice interaction failed")

        self._set_state(ActivationState.LISTENING)

    def _show_notification(self, title: str, message: str) -> None:
        """Show a macOS system notification for visual feedback."""
        import os
        os.system(f"osascript -e 'display notification \"{message}\" with title \"{title}\"'")

    def _set_state(self, new_state: ActivationState) -> None:
        """Update state with logging."""
        old = self._state
        self._state = new_state
        if old != new_state:
            logger.debug("State: %s → %s", old.value, new_state.value)


