from src.utils.logger import get_logger
import threading
import time
import queue
from enum import Enum
from typing import Callable, Optional
from src.core.context_manager import FollowUpContextManager

logger = get_logger("friday.activation")

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
        skip_face_verification: bool = False,
        load_brain: bool = True,
    ) -> None:
        self.boss_encodings_path = boss_encodings_path
        self.on_boss_verified = on_boss_verified
        self.on_stranger = on_stranger
        self.on_no_face = on_no_face
        self.camera_index = camera_index
        self.skip_face_verification = skip_face_verification
        self.load_brain = load_brain

        self._state = ActivationState.IDLE
        self._lock = threading.Lock()
        self._event_queue = queue.Queue()
        self._running = False
        self.context_manager = FollowUpContextManager()

        # Components
        self._wake_word = None
        self._face_recognizer = None
        self._stt = None
        self._tts = None
        self._voice_pipeline = None
        self.ipc_bridge = None
        self._passive_listen_thread = None
        self._passive_listen_abort = None

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

        # Initialize face recognizer (skip if configured)
        if not self.skip_face_verification:
            from src.modules.vision.face_recognizer import VisionFaceRecognizer
            self._face_recognizer = VisionFaceRecognizer(
                boss_encodings_path=self.boss_encodings_path,
                camera_index=self.camera_index,
            )
        else:
            logger.info("Face verification disabled — skipping recognizer init")

        # Initialize voice pipeline
        from src.modules.audio.stt import SpeechToText
        from src.modules.audio.tts import TextToSpeech
        from src.modules.voice_pipeline import VoicePipeline

        self._stt = SpeechToText()
        self._tts = TextToSpeech()

        # Initialize floating glowing overlay (skip if running under native Swift UI)
        import os
        if os.getenv("FRIDAY_NO_OVERLAY") == "1":
            logger.info("Legacy Tkinter overlay disabled (running under native Swift UI)")
            self.overlay = None
        else:
            from src.utils.overlay import FridayOverlay
            self.overlay = FridayOverlay()
            self.overlay.start()

        brain = None
        if self.load_brain:
            try:
                from src.core.brain import FridayBrain
                brain = FridayBrain()
                brain.load_model()
                logger.info("Brain loaded — full voice interaction ready")
            except Exception as e:
                logger.warning("Brain not available: %s", e)
        else:
            logger.info("Brain loading disabled via --no-brain flag")

        self._voice_pipeline = VoicePipeline(stt=self._stt, tts=self._tts, brain=brain)
        
        # Inject voice_pipeline, activation_handler, and tool_server into proactive engine
        # so it can speak reminders AND check pipeline state before doing so
        if brain and getattr(brain, "proactive_engine", None):
            brain.proactive_engine.voice_pipeline = self._voice_pipeline
            brain.proactive_engine.activation_handler = self
            from src.tools.server import MCPToolServer
            self._tool_server = MCPToolServer()
            brain.proactive_engine._tool_server = self._tool_server
        
        self._running = True
        self._wake_word.start()

        # Initialize IPC bridge for menu bar communication
        from src.core.ipc_bridge import IPCBridge
        self.ipc_bridge = IPCBridge(activation_handler=self)
        self.ipc_bridge.start()

        # Inject references for real-time visualizer updates
        self._voice_pipeline.ipc_bridge = self.ipc_bridge
        self._voice_pipeline.activation_handler = self

        self._set_state(ActivationState.LISTENING)
        logger.info("Activation handler started — listening for wake word")

    def _abort_passive_listen(self) -> None:
        """Abort and join the background passive follow-up listen thread if active."""
        if hasattr(self, "_passive_listen_abort") and self._passive_listen_abort:
            self._passive_listen_abort.set()
        if hasattr(self, "_passive_listen_thread") and self._passive_listen_thread:
            self._passive_listen_thread.join(timeout=1.0)
            self._passive_listen_thread = None
            self._passive_listen_abort = None

    def _run_passive_listen(self) -> None:
        """Runs short passive listen session on background thread for smart follow-up."""
        try:
            logger.debug("Smart follow-up active listening thread started...")
            listen_result = self._stt.listen(timeout=3.0, abort_event=self._passive_listen_abort)
            if self._passive_listen_abort and self._passive_listen_abort.is_set():
                return

            if isinstance(listen_result, tuple):
                transcript, detected_lang = listen_result
            else:
                transcript, detected_lang = listen_result, "en"

            if transcript and self.context_manager.is_followup_eligible(transcript):
                self._event_queue.put(("follow_up", transcript))
        except Exception as e:
            logger.error("Smart follow-up passive listen failed: %s", e)

    def run_loop(self) -> None:
        """
        Main execution loop. MUST BE CALLED FROM THE MAIN THREAD.
        Processes events like wake word detections and runs camera/brain logic.
        """
        logger.debug("Main loop started")
        try:
            while self._running:
                try:
                    # Non-blocking check for events with small timeout to allow smooth UI updates
                    event = self._event_queue.get(timeout=0.02)
                    if event == "wake_word":
                        self._abort_passive_listen()
                        self._handle_activation()
                    elif isinstance(event, tuple) and event[0] == "follow_up":
                        transcript = event[1]
                        self._abort_passive_listen()
                        if (
                            self._state == ActivationState.LISTENING
                            and self.context_manager.is_followup_window_active()
                        ):
                            logger.info("🔥 Smart follow-up triggered: '%s'", transcript)
                            self._set_state(ActivationState.PROCESSING)
                            self._handle_direct_voice_interaction(transcript)
                except queue.Empty:
                    pass

                # Check for smart follow-up activation
                if (
                    self._state == ActivationState.LISTENING
                    and self.context_manager.is_followup_window_active()
                ):
                    if not self._passive_listen_thread or not self._passive_listen_thread.is_alive():
                        self._passive_listen_abort = threading.Event()
                        self._passive_listen_thread = threading.Thread(
                            target=self._run_passive_listen,
                            name="friday-passive-listen",
                            daemon=True
                        )
                        self._passive_listen_thread.start()

                # Update the Tkinter overlay frame on the main thread if active
                if hasattr(self, "overlay") and self.overlay:
                    self.overlay.update()
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Stop all activation components."""
        self._running = False
        self._abort_passive_listen()
        if self._wake_word:
            self._wake_word.stop()
        if self._tts:
            self._tts.stop()
        if self.ipc_bridge:
            self.ipc_bridge.stop()
        if hasattr(self, "overlay") and self.overlay:
            self.overlay.stop()
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

        # Signal abort early to background passive listen so it frees the microphone
        if hasattr(self, "_passive_listen_abort") and self._passive_listen_abort:
            self._passive_listen_abort.set()

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

        # If face verification is disabled, skip straight to READY
        if self.skip_face_verification:
            logger.info("✅ Face verification skipped — proceeding as boss")
            self._set_state(ActivationState.READY)
            threading.Thread(target=self.on_boss_verified, daemon=True).start()
            self._handle_voice_interaction()
            return
        
        start = time.perf_counter()
        try:
            identity, name = self._face_recognizer.verify_identity(
                camera_index=self.camera_index
            )
            latency = time.perf_counter() - start

            if identity == "boss":
                logger.info("✅ Boss verified in %.2fs", latency)
                self._set_state(ActivationState.READY)
                
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

            # Set state to READY so that the listening animation plays while recording speech.
            self._set_state(ActivationState.READY)
            
            result = self._voice_pipeline.process_voice_command(timeout=10, return_tuple=True)

            if isinstance(result, tuple):
                command, response = result
            else:
                command, response = None, result

            if response:
                logger.info("Voice command completed successfully")
                if command:
                    self.context_manager.record_response(command, response)
            else:
                self._set_state(ActivationState.SPEAKING)
                self._tts.speak("I didn't hear anything.", blocking=True)

        except Exception:
            logger.exception("Voice interaction failed")

        self._set_state(ActivationState.LISTENING)

    def _handle_direct_voice_interaction(self, transcript: str) -> None:
        """Run the voice pipeline directly with pre-transcribed text (Executed on Main Thread)."""
        if not self._voice_pipeline:
            self._set_state(ActivationState.LISTENING)
            return

        try:
            if self._tts:
                self._tts.reset_preempt()

            self._set_state(ActivationState.PROCESSING)
            result = self._voice_pipeline.process_voice_command(
                timeout=10,
                return_tuple=True,
                pre_transcribed_command=transcript
            )

            if isinstance(result, tuple):
                command, response = result
            else:
                command, response = None, result

            if response:
                logger.info("Voice command completed successfully")
                if command:
                    self.context_manager.record_response(command, response)
            else:
                self._set_state(ActivationState.SPEAKING)
                self._tts.speak("I didn't hear anything.", blocking=True)

        except Exception:
            logger.exception("Direct voice interaction failed")

        self._set_state(ActivationState.LISTENING)

    def _set_state(self, new_state: ActivationState | str) -> None:
        """Update state with logging and IPC bridge notification."""
        if isinstance(new_state, str) and not isinstance(new_state, ActivationState):
            try:
                new_state = ActivationState(new_state)
            except ValueError:
                pass

        old = self._state
        self._state = new_state
        if old != new_state:
            old_val = old.value if hasattr(old, "value") else str(old)
            new_val = new_state.value if hasattr(new_state, "value") else str(new_state)
            logger.debug("State: %s → %s", old_val, new_val)
            if self.ipc_bridge:
                self.ipc_bridge.write_status(new_val)
            
            # Control overlay visibility and colors based on state
            if hasattr(self, "overlay") and self.overlay:
                if new_state in (ActivationState.VERIFYING, ActivationState.READY, ActivationState.PROCESSING, ActivationState.SPEAKING):
                    self.overlay.show(new_val)
                else:
                    self.overlay.hide()


