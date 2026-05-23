# Implementation Plan — Phase Set 5: Security Hardening, Bilingual STT & Formal Academic Paper

This plan details the design and execution steps for Phase Set 4 (Phases 12, 13, and 14) of Project F.R.I.D.A.Y. We will implement runtime security guards, auto-detected bilingual STT routing with cloud fallback for Hindi, automated concurrent/unload race tests, long-running soak-testing profiles, full benchmarks, and write the final academic research paper.

---

## User Review Required

> [!IMPORTANT]
> - **Bilingual STT Privacy Tradeoff**: Direct auto-routing to the Sarvam AI API for Hindi speech means audio data leaves the local device when Hindi is spoken. This is a documented, user-approved exception to the local-first architecture and will be formally highlighted in the research paper's security and privacy sections.
> - **Model Agnosticism in Prompting**: XML tool calls from the brain in response to Hindi inputs will be generated in pure ASCII JSON (avoiding Devanagari inside the JSON payload) to ensure that the regex-based `MCPToolServer` parsing remains fully stable and compatible.

---

## Proposed Changes

### Component 1: Security Hardening (Phase 12)

#### [MODIFY] [file_tool.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/tools/file_tool.py)
* Scan file read payloads for known prompt injection patterns (e.g. `ignore previous instructions`, `you are now a`, `<|system|>`, etc.).
* Wrap matching payloads in neutral `[FILE CONTENT START]` and `[FILE CONTENT END]` markers to instruct the LLM to treat them purely as data, returning a security warning flag in the tool results dict.

#### [MODIFY] [server.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/tools/server.py)
* Add a rolling 60-second sliding window tool calling counter in `MCPToolServer`.
* Hard-constrain execution to a maximum of 5 tool calls within this window, returning a rate limit error JSON block to prevent infinite prompt loops.

#### [MODIFY] [brain.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/brain.py)
* Enforce a strict input character ceiling (`500` characters) on `user_message` inside `think_full()`, truncating any excessively long transcriptions to prevent context window bloating or overflow attacks.

#### [NEW] [test_concurrent_tts_arbitration.py](file:///Users/khatuaryan/PycharmProjects/Friday/tests/integration/test_concurrent_tts_arbitration.py)
* Add an integration test to formally validate active ProactiveEngine TTS interruption when the wake word is detected mid-speech.
* Asserts immediate termination (`killall say` signal -15) and safe transition into the `VERIFYING` state.

#### [NEW] [test_rag_unload_race.py](file:///Users/khatuaryan/PycharmProjects/Friday/tests/unit/test_rag_unload_race.py)
* Add a race-condition unit test verifying that if the lazy embedding model's 5-minute auto-unload daemon triggers simultaneously with an active thread vector search, `sqlite-vec`'s `RLock` serializes the operations cleanly to avoid segfaults or `NoneType` errors.

#### [NEW] [soak_test.py](file:///Users/khatuaryan/PycharmProjects/Friday/scripts/soak_test.py)
* Write a 4-hour soak testing script simulating active periodic user work cycles.
* Polls RSS memory metrics to detect leaks or memory creep (>50MB), writing a structured report to `docs/research-paper/benchmarks/soak-test.txt`.

---

### Component 2: Bilingual STT (Phase 13)

#### [MODIFY] [friday_config.yaml](file:///Users/khatuaryan/PycharmProjects/Friday/config/friday_config.yaml)
* Update the STT settings block to target `mlx-community/whisper-small.mlx` (multilingual model).
* Register the `sarvam` API properties (`endpoint`, `language_code="hi-IN"`, `model="saarika:v2"`).

#### [MODIFY] [stt.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/modules/audio/stt.py)
* Initialize `sarvam_api_key` using environment variables. Log a warning if the key is missing.
* Auto-detect spoken language locally by passing `language=None` to `mlx_whisper.transcribe`.
* If language detected is English (`en`), return the local transcription.
* If Hindi (`hi`) is detected and the Sarvam API key is configured, post the audio bytes to the Sarvam API endpoint for high-precision Hindi text synthesis.
* Fall back gracefully to the local multilingual Whisper transcription if the API fails or is unconfigured.
* Return a `(text, language_code)` tuple from `listen()`.

#### [MODIFY] [voice_pipeline.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/modules/voice_pipeline.py)
* Adapt `process_voice_command()` to parse the returned text and language tuple.
* Pass the `detected_language` parameter directly to the brain's reasoning entry point.
* Return Hindi fallbacks for brain processing errors if the input language is Hindi.

#### [MODIFY] [prompts.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/prompts.py)
* Add a `user_language` parameter to `build_full_system_prompt()`.
* If `user_language == "hi"`, inject bilingual instructions telling the model to respond in concise natural Hindi or Hinglish spoken prose under 50 words, while strictly keeping intermediate `<tool_call>` JSON payloads in English ASCII format.

#### [MODIFY] [test_stt.py](file:///Users/khatuaryan/PycharmProjects/Friday/tests/unit/test_stt.py)
* Add unit tests verifying `listen()`'s tuple return types, missing API key warning logs, and mock-based Sarvam routing logic.

---

### Component 3: Academic Benchmarking & Paper (Phase 14)

#### [NEW] [benchmark_tool_loop.py](file:///Users/khatuaryan/PycharmProjects/Friday/scripts/benchmark_tool_loop.py)
* Implement a programmatic benchmark run firing 20 isolated calendar queries under normal and simulated warning memory pressure.
* Logs successes, infinite loops, and hallucinations to `docs/research-paper/benchmarks/tool-loop-benchmark.json`.

#### [NEW] [benchmark_roundtrip.py](file:///Users/khatuaryan/PycharmProjects/Friday/scripts/benchmark_roundtrip.py)
* Measure programmatic end-to-end voice latency breakdowns (STT transcription, Brain with/without tool calls), documenting placeholders for manual stopwatch components (Face verification and TTS start).

#### [NEW] [benchmark_stt_accuracy.py](file:///Users/khatuaryan/PycharmProjects/Friday/scripts/benchmark_stt_accuracy.py)
* Formulate programmatic and manual Word Error Rate (WER) scoring definitions for local English transcriptions and local vs. cloud Hindi routing.

#### [NEW] [FRIDAY_paper.md](file:///Users/khatuaryan/PycharmProjects/Friday/docs/research-paper/FRIDAY_paper.md)
* Write a publication-grade, formal academic research paper structuring the entire F.R.I.D.A.Y. design, memory management profiles, multi-sensor pipelines, RAG memory designs, and benchmarks.

---

## Verification Plan

### Automated Verification
* Execute the complete testing suite to guarantee that all 54 existing tests, along with the newly introduced unit and integration tests, pass flawlessly:
  ```bash
  pytest tests/ -v
  ```

### Manual Verification & Dynamic Tests
1. **Prompt Injection Wrap Check**: Trigger the custom check using an injection file to ensure the content is correctly wrapped and the warning flag is returned.
2. **Rate Limiting Check**: Assert that making more than 5 tool calls within 60 seconds returns the sliding-window error.
3. **Bilingual Routing Verification**:
   * Set `SARVAM_API_KEY` in `.env` and verify that speaking English results in local Whisper processing.
   * Speak Hindi and verify routing to the Sarvam API with correct transcription delivery.
4. **Latency & Success Profiles**: Run the tool loop and roundtrip benchmark scripts to verify metrics are outputted correctly.
