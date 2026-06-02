# Phase 8 — Personalized Engineering Prompt

> **Instructions for the implementer:** Read this entire document before writing a single line of code. This prompt captures the exact desired behavior, codebase context, and constraints. Build strictly from this spec.

---

## 🎯 What We're Building

F.R.I.D.A.Y. is a macOS native AI assistant. It runs a **Python core** (wake word → face ID → STT → LLM → TTS) alongside a **SwiftUI menu-bar app** (`FridayUI`). They communicate via a **file-based IPC bridge**: Python writes `~/.cache/friday/status.json`, Swift polls it every 100ms and reacts to state changes.

Phase 8 adds three things:

1. **Lottie Animation HUD** — a floating overlay in the top-right corner of the screen, showing state-specific Lottie JSON animations (listening / thinking / responding). Vector-based, resolution-independent, true alpha transparency. It appears when the wake word fires and disappears only after the full response ends.
2. **Response Text Bubble** — a slim, styled text box directly below the animation showing the transcribed command and Friday's response.
3. **Smart Follow-Up Detection** — removing the requirement to say "hey mycroft" for follow-up questions within a conversation context window.

---

## 🗂 Codebase Architecture You Must Know

### Python Core (`src/`)

| File | Role |
|------|------|
| `src/core/activation_handler.py` | Master state machine. Controls `IDLE → LISTENING → VERIFYING → READY → PROCESSING → SPEAKING`. Calls `_set_state()` which writes IPC + controls legacy Tkinter overlay. |
| `src/core/ipc_bridge.py` | Writes `~/.cache/friday/status.json` with `{ state, timestamp, rss_mb, pressure, pid }`. Also polls `~/.cache/friday/commands/` for `.cmd` files sent by Swift. |
| `src/modules/audio/wake_word.py` | Continuous OpenWakeWord detector on background thread. Fires `_queue_wake_word()` callback when "hey_mycroft" confidence > threshold. 2s cooldown. |
| `src/modules/voice_pipeline.py` | `process_voice_command()`: STT listen → brain.think → TTS speak. Returns response text. |
| `src/modules/audio/tts.py` | `speak(text, blocking)` — macOS `say` subprocess. Supports preempt. |

### Swift App (`FridayUI/`)

| File | Role |
|------|------|
| `FridayUI/App/FridayUIApp.swift` | App entry. Hosts `MenuBarExtra` + `WindowGroup` for floating HUD. |
| `FridayUI/Core/IPCBridge.swift` | `@Published var state: String`. Polls status.json every 100ms. Sends commands by writing `.cmd` files. |
| `FridayUI/Views/FloatingHUDWindow.swift` | The transparent window sitting top-right. Currently shows `GlowingOrbView`. Positioned 160×160 at `screenFrame.maxX - 160 - 16`. |
| `FridayUI/Views/GlowingOrbView.swift` | Animated neon orb with per-state colors (cyan/purple/pink). Currently the only visual indicator. |

---

## 🎨 Feature 1: Lottie Animation Overlay

### Behavior
- The animation **appears immediately** when wake word fires (state transitions from `listening` to `verifying`).
- It **stays visible** through `verifying → ready → processing → speaking`.
- It **disappears** only when state returns to `listening` (response fully delivered) or `idle`/`offline`.
- Three Lottie JSON files correspond to three state groups:
  - `listening.json` → shown during `verifying` and `ready`
  - `thinking.json` → shown during `processing`
  - `responding.json` → shown during `speaking`

### Lottie JSON Assets
The animations are designed in SVGator and exported as Lottie JSON with the following settings:
- **Type:** Animated
- **Exported IDs:** None (minimal JSON size)
- **Optimized JSON:** Enabled
- **Frame rate:** 60 fps (smooth yet CPU-efficient on macOS)
- **Speed:** 100% (baseline; adjustable in code)
- **Canvas color / "Include in export":** **Unchecked** (transparent background — the animation floats directly over the desktop)

The files are located at:
```
FridayUI/App/animations/listening.json
FridayUI/App/animations/thinking.json
FridayUI/App/animations/responding.json
```

### Why Lottie over GIF
- **True alpha transparency** — no pixelated edges or halo artifacts that plague GIF's 1-bit alpha
- **Vector-based** — renders pixel-perfect at any scale or Retina density
- **Tiny file size** — typically 5–50 KB vs. 500 KB–2 MB for equivalent GIFs
- **Dynamic control** — playback speed, looping, color tinting, and progress scrubbing are all programmatically adjustable

### Swift Integration: Lottie Player

> **Important:** SwiftUI has no native Lottie renderer. Use the open-source **[lottie-ios](https://github.com/airbnb/lottie-ios)** library (v4.x) via Swift Package Manager.

**SPM dependency to add in Xcode:**
```
https://github.com/airbnb/lottie-ios.git
```
Minimum version: `4.4.0`. Target: `FridayUI`.

**New file:** `FridayUI/Views/LottieAnimationView.swift`

Create an `NSViewRepresentable` wrapper around `LottieAnimationView` (from the lottie-ios package):

```swift
import SwiftUI
import Lottie

struct LottiePlayerView: NSViewRepresentable {
    let animationName: String   // e.g. "listening", "thinking", "responding"
    var loopMode: LottieLoopMode = .loop
    
    class Coordinator {
        var currentAnimationName: String?
    }
    
    func makeCoordinator() -> Coordinator {
        Coordinator()
    }
    
    func makeNSView(context: Context) -> LottieAnimationView {
        let view = LottieAnimationView(name: animationName, bundle: .main)
        view.loopMode = loopMode
        view.contentMode = .scaleAspectFit
        view.backgroundBehavior = .pauseAndRestore
        view.play()
        context.coordinator.currentAnimationName = animationName
        return view
    }
    
    func updateNSView(_ nsView: LottieAnimationView, context: Context) {
        // If the animation name changed (state transition), swap the animation compiler-safely
        if context.coordinator.currentAnimationName != animationName {
            context.coordinator.currentAnimationName = animationName
            nsView.animation = LottieAnimation.named(animationName, bundle: .main)
            nsView.play()
        }
    }
}
```

### Implementation Notes
- Replace `GlowingOrbView` inside `FloatingHUDWindow.swift` with `LottiePlayerView`, choosing the animation name based on `ipc.state`.
- The `GlowingOrbView` remains in the project as a **fallback** if the Lottie JSON files are missing (e.g., `if Bundle.main.path(forResource: animName, ofType: "json") == nil { /* show orb */ }`).
- The window size should expand to accommodate both the animation (top) and the response text bubble (bottom). Suggested new window size: `width: 280, height: 360`.
- Keep `window.level = .statusBar` and `.canJoinAllSpaces` behaviors.
- Use `withAnimation(.easeInOut(duration: 0.3))` wrapping state transitions for smooth appearance/disappearance.
- Copy the `.json` files into the Xcode project's bundle resources under `FridayUI/App/animations` so Xcode synchronizes them automatically.
- **Removed macOS System Alerts**: Eliminated all redundant, disruptive `display notification` system popups across `activation_handler.py` to yield a clean, premium background process UX entirely driven by the floating overlay HUD.

---

## 💬 Feature 2: Response Text Bubble

### Layout (top → bottom in the HUD window)
```
┌─────────────────────────────────┐
│  [Lottie Animation — 160×160]   │
│                                 │
│  ┌───────────────────────────┐  │
│  │ 👤 You: "what's the time" │  │
│  │ 🤖 It is 3:42 PM.         │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

### Behavior
- The bubble appears **alongside** the animation — same moment (wake word fires).
- Shows the transcribed user command as soon as STT completes (i.e., when state = `processing`).
- Shows Friday's response text as TTS begins (state = `speaking`).
- Clears and hides when animation hides (state = `listening` or `idle`).

### IPC Extension Required
To pass the **text content** to Swift, extend `status.json` with two new optional fields:

```json
{
  "state": "speaking",
  "timestamp": "...",
  "rss_mb": 42.1,
  "pressure": "normal",
  "pid": 12345,
  "last_command": "what is the time right now",
  "last_response": "It is 3:42 PM, Boss."
}
```

**Python side** (`ipc_bridge.py`):
- Add `last_command: str = ""` and `last_response: str = ""` to the IPC payload.
- These are updated by the `VoicePipeline` before and after the brain call:
  - Write `last_command` just after STT returns text.
  - Write `last_response` just after brain returns the response text.

**Swift side** (`IPCBridge.swift`):
- Add `@Published var lastCommand: String = ""` and `@Published var lastResponse: String = ""`.
- Parse from `status.json` in `pollStatus()`.

### Styling
- Dark translucent background: `Color.black.opacity(0.75)` with `cornerRadius(12)`.
- User text in `.caption` weight, muted color.
- Response text in `.body` weight, white or near-white.
- Max 4 lines; overflow truncates with ellipsis.
- Subtle slide-up + fade-in animation on appearance.

---

## 🧠 Feature 3: Smart Follow-Up Detection (No Wake Word Required)

### The Problem
Currently, after every complete response, the user must say "hey mycroft" again to talk to Friday — even for immediate follow-ups. This is unnatural and breaks conversational flow.

### The Solution: Context Window Detection
After a successful response, the system enters a **"follow-up window"** for a configurable duration (default: **15 seconds**). During this window:
- **No wake word is required.** Friday auto-activates listening immediately.
- The microphone listens for ambient speech in a low-power passive mode.
- If speech is detected, it runs through the same STT → Brain → TTS pipeline.

### Follow-Up Eligibility Rules (Python logic, `activation_handler.py`)

A follow-up is **eligible** (no wake word needed) if **all** of the following are true:
1. The last response completed **< 15 seconds ago** (configurable via `FRIDAY_FOLLOWUP_WINDOW_SECS` env var).
2. The detected speech starts with a **conjunction or continuation phrase** — e.g.: *"and", "also", "but", "what about", "how about", "so", "then", "what if", "why", "when", "ok", "alright"* — OR does NOT start with a proper noun / third-person name (heuristic for "is the boss talking to me?").
3. The **topic similarity** score (simple word-overlap Jaccard with last command context) is > 0.15 OR the user explicitly addresses Friday (e.g., starts with "and you", "what else").

### "Is the Boss Talking to Me?" Detection
If the speech starts with a third-person name that is not "Friday" or a known alias, treat it as ambient conversation and **do not activate**. Examples:
- "tell Rohan about the meeting" → Don't activate (talking to/about someone else)
- "and what about the budget?" → Activate (follow-up to previous context)
- "hey Friday, ..." → Always activate (explicit address)

### Implementation Details

**New file:** `src/core/context_manager.py`

```python
class FollowUpContextManager:
    def __init__(self, window_secs: int = 15):
        self.window_secs = window_secs
        self.last_response_time: float = 0.0
        self.last_command: str = ""
        self.last_response: str = ""
        
    def record_response(self, command: str, response: str) -> None:
        """Call after every successful response."""
        ...
    
    def is_followup_window_active(self) -> bool:
        """True if within the time window after last response."""
        ...
    
    def is_followup_eligible(self, transcript: str) -> bool:
        """
        Returns True if this transcript qualifies as a follow-up
        and wake word can be skipped.
        """
        ...
```

**Modification to `activation_handler.py`:**
- After `_handle_voice_interaction()` completes successfully, call `context_manager.record_response(command, response)`.
- In `run_loop()`, after the main wake-word event loop, add a **passive listening check**:
  - If `context_manager.is_followup_window_active()`: start a short passive listen (2–3s).
  - If speech detected AND `context_manager.is_followup_eligible(transcript)`: skip wake word, go directly to `PROCESSING`.

**Modification to `voice_pipeline.py`:**
- Return both `(command_text, response_text)` from `process_voice_command()` so `activation_handler` can pass them to `context_manager`.

---

## ⚡ Latency Reduction Suggestions (Do NOT implement — informational only)

The user is aware of the current latency between command and response. Here are the strategies to reduce it (for future phases):

1. **Streaming TTS with sentence-boundary chunking** — Already partially implemented for conversational queries. Extend to ALL response types, not just `is_conversational` flag.
2. **STT warm-up** — Pre-load Whisper/STT model on startup instead of lazy-loading on first use.
3. **Parallel STT + context fetch** — Start fetching memory context while STT is still transcribing.
4. **Local model fallback** — For simple queries (time, date, simple math), use a 1B local model (e.g., `Phi-3-mini`) running on-device via `llama.cpp` for sub-100ms responses.
5. **OpenRouter HTTP/2 keep-alive** — Reuse the connection instead of creating a new TCP session per request.
6. **Predictive prefill** — After STT starts, send partial transcript to the LLM every 0.5s as a streaming prefix so the model starts generating before the user finishes speaking.

---

## 🧱 File Change Summary

| File | Change Type | Reason |
|------|-------------|--------|
| `FridayUI/Views/FloatingHUDWindow.swift` | Modify | Larger window, add Lottie player + response bubble |
| `FridayUI/Views/GlowingOrbView.swift` | Keep | Fallback if Lottie JSON not found |
| `FridayUI/Views/LottieAnimationView.swift` | **New** | `NSViewRepresentable` wrapping lottie-ios `LottieAnimationView` |
| `FridayUI/Views/ResponseBubbleView.swift` | **New** | The text bubble showing command + response |
| `FridayUI/Core/IPCBridge.swift` | Modify | Add `lastCommand`, `lastResponse` published properties |
| `src/core/ipc_bridge.py` | Modify | Add `last_command`, `last_response` to status payload |
| `src/core/activation_handler.py` | Modify | Integrate follow-up context manager; pass texts to IPC |
| `src/modules/voice_pipeline.py` | Modify | Return `(command, response)` tuple instead of just response |
| `src/core/context_manager.py` | **New** | `FollowUpContextManager` class |
| `FridayUI/App/animations/listening.json` | **New** | Lottie animation resource for listening/verifying state |
| `FridayUI/App/animations/thinking.json` | **New** | Lottie animation resource for processing state |
| `FridayUI/App/animations/responding.json` | **New** | Lottie animation resource for speaking state |
| `FridayUI.xcodeproj` | Modify | Add lottie-ios SPM dependency + package linking |

---

## ✅ Acceptance Criteria

- [ ] Lottie animation appears exactly when wake word fires; disappears when response ends
- [ ] Correct Lottie JSON plays for each state (listening/thinking/responding)
- [ ] Animations render with true alpha transparency over the desktop (no background artifacts)
- [ ] Graceful fallback to `GlowingOrbView` if Lottie JSON files are missing from bundle
- [ ] Response bubble shows user command during `processing`, Friday's response during `speaking`
- [ ] Text bubble clears gracefully when HUD hides
- [ ] Follow-up commands within 15s don't require "hey mycroft"
- [ ] Ambient conversation (boss talking to someone else) does not trigger activation
- [ ] Explicit "hey mycroft" always works regardless of context window
- [ ] All new Python code has type hints and docstrings
- [ ] All new Swift views use the existing `IPCBridge` @ObservedObject pattern
- [ ] No regressions to existing menu bar, hotkey, or daemon lifecycle functionality
