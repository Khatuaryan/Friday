# Phase Set 2: Voice & Brain Integration

Phases 3–5 transform F.R.I.D.A.Y. from a "wake + verify" demo into a fully conversational assistant with high-cognition cloud reasoning, sub-second sentence-by-sentence streaming voice synthesis, and local tool execution capability.

---

## Technical Architecture & Design Choices

1. **Native `NSSpeechSynthesizer` Streaming**:
   - Instead of loading heavy local neural speech models (like Piper or Kokoro ONNX which consume 200MB+ of RAM), F.R.I.D.A.Y. uses the native macOS `NSSpeechSynthesizer` through `PyObjC` bindings or shell invocation.
   - Perceived voice latency is reduced to **under 1 second** by splitting final synthesized responses into individual sentences and streaming them to the audio hardware incrementally with `blocking=False`.
2. **Auto-Detected Bilingual STT**:
   - Local STT uses `mlx-community/whisper-small-mlx` (~600MB footprint) optimized for Apple Silicon Unified Memory.
   - On listening, the model detects the spoken language. If Hindi (`hi`) is detected, the pipeline automatically routes the raw int16 frames to the **Sarvam AI STT API** for high-precision Hindi script output, falling back to local multilingual Whisper if the network drops or the key is absent.
3. **Conversational Speech Persona**:
   - Prompts instruct the system to speak in a charming, helpful F.R.I.D.A.Y.-like persona, addressing the user as "Boss" in Hinglish/Hindi or English, returning concise verbal responses under 50 words.

---

## Proposed Changes

### Component 1: Voice Pipeline (STT + TTS) (Phase 3)

#### [Audio Modules]

##### [MODIFY] [stt.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/modules/audio/stt.py)
* Initialize `sarvam_api_key` using environment variables. Log a warning if the key is missing.
* Pass `language=None` to `mlx_whisper.transcribe` to enable automatic language detection.
* If language detected is English (`en`), return the local transcription.
* If Hindi (`hi`) is detected and the Sarvam API key is configured, post the audio bytes to the Sarvam API endpoint for high-precision Hindi text synthesis, falling back to local multilingual Whisper if the API fails or is unconfigured.
* Return a `(text, language_code)` tuple from `listen()`.

##### [MODIFY] [tts.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/modules/audio/tts.py)
* Implement sentence-by-sentence streaming logic. Split the incoming text stream into complete sentences.
* Call native macOS speech synthesizers asynchronously using `blocking=False` inside a dedicated audio stream playback thread to start speaking immediately as individual sentences are generated, keeping perceived speech start latency under 1 second.
* Provide a robust `stop()` function executing `killall say` to purge all system speech buffers instantly on preemption signals.

##### [MODIFY] [voice_pipeline.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/modules/voice_pipeline.py)
* Adapt `process_voice_command()` to parse the returned text and language tuple from `listen()`.
* Pass the `detected_language` parameter directly to the brain's reasoning entry point.
* Return Hindi/Hinglish fallbacks for brain processing errors if the input language is Hindi.

---

### Component 2: Brain Integration (Phase 4)

##### [MODIFY] [brain.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/brain.py)
* Maintain a strict, rolling 10-turn conversation history constraint to keep contexts small, avoiding bloated RAM consumption.
* Refactor the system messages assembler to support dynamic OpenRouter chat history formats.
* Injects prompt guidelines restricting spoken voice replies to be concise, natural, and strictly under 50 words (max 300 characters).

##### [MODIFY] [prompts.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/prompts.py)
* Injects Hinglish/Hindi or English F.R.I.D.A.Y. persona guidelines based on `user_language`.

---

## Verification Plan

### Automated Tests
* Run the dedicated STT and TTS unit tests to ensure robust validation:
  ```bash
  pytest tests/unit/test_stt.py
  pytest tests/unit/test_tts.py
  ```

### Manual Verification
1. Boot F.R.I.D.A.Y.: `python -m src.core`.
2. Speak English and Hindi conversational commands. Verify that ASR detects languages correctly, routes Hindi to Sarvam AI, and F.R.I.D.A.Y. answers with under 1 second voice speech start delay.
3. Verify that the floating visualizer orb pulses dynamically in sync with speaking audio amplitudes.
