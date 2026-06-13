# Implementation Plan — FridayUI & Python Core Refactor and Fixes

This implementation plan details the fixes for the 7 issues identified in FridayUI and the F.R.I.D.A.Y. Python daemon, achieving a Siri-like macOS companion app.

---

## Proposed Changes

### SwiftUI native interface (`FridayUI/`)

#### [MODIFY] [project.pbxproj](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/FridayUI.xcodeproj/project.pbxproj)
- Add `INFOPLIST_KEY_LSUIElement = YES;` under both Debug and Release `XCBuildConfiguration` build settings blocks for the main `FridayUI` target. This hides the app icon from the macOS Dock.

#### [MODIFY] [FridayUIApp.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/App/FridayUIApp.swift)
- Remove `WindowGroup` entirely.
- Move lifecycle logic, `DaemonManager` instantiation, and `IPCBridge` instantiation to `AppDelegate`.
- Initialize services, register global hotkeys, and setup the programmatic `NSPanel` during `applicationDidFinishLaunching` to ensure the HUD and hotkey work immediately on app boot.

#### [MODIFY] [FloatingHUDWindow.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/Views/FloatingHUDWindow.swift)
- Simplify view body by removing `WindowConfigurator` and direct window configuration logic.
- Add `.onChange(of: ipc.state)` and `.onAppear` handlers to dynamically toggle `ignoresMouseEvents` on the hosting `NSPanel` so that the HUD is click-through when hidden/idle, but clickable when showing active animations.

#### [MODIFY] [GlobalHotkeyManager.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/Core/GlobalHotkeyManager.swift)
- Store local and global monitor references.
- Add `isRegistered` flag guard to prevent duplicate event listener leak.
- Add `unregister()` helper.

#### [MODIFY] [DaemonManager.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/Core/DaemonManager.swift)
- Clean up any stale PID file if the process is dead synchronously prior to running startup checks.
- Add `--no-face` argument to python process arguments to skip face verification by default, cutting activation latency.

#### [MODIFY] [MenuDropdownView.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/Views/MenuDropdownView.swift)
- Remove the unused `requestPermissions()` method which requested camera/mic access from SwiftUI, avoiding macOS permission alerts and mic device contention.

#### [DELETE] [ContentView.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/App/ContentView.swift)
- Delete this file since it is unused debug code that duplicates core service instantiations.

---

### Python Core Components

#### [MODIFY] [stt.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/modules/audio/stt.py)
- Support an optional `abort_event` parameter in `SpeechToText.listen()`.
- Periodically check this event inside the VAD loop and wait loops. If aborted, instantly stop recording, release PyAudio stream, and return early without transcribing.

#### [MODIFY] [activation_handler.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/activation_handler.py)
- Move passive follow-up listening out of the main thread and into a background thread (`self._passive_listen_thread`).
- Before starting any active conversation flow (via wake word or hotkey), signal the background passive listen thread to abort and join it using `_passive_listen_abort.set()` and `join()`, freeing the microphone.
- Set the activation state to `ActivationState.READY` instead of `PROCESSING` prior to invoking `process_voice_command`, enabling the Siri listening animation to run while recording audio.
- Remove the blocking greeting TTS `self._tts.speak("Hey Boss, how can I help?", blocking=True)`.

#### [MODIFY] [engine.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/proactive/engine.py)
- Replace `display notification` command execution with a function that routes the title and message through the IPC bridge so they are rendered directly in the native Swift HUD.

---

## Verification Plan

### Automated Tests
- Run full Python test suite:
  ```bash
  make test
  ```

### Manual Verification
- Verify FridayUI has no Dock icon and runs solely from the macOS menu bar.
- Test Option+Space global hotkey; check that HUD panel displays Siri animation in top-center of screen.
- Verify HUD is click-through when hidden.
- Verify "Hey Mycroft" wake word activates listening.
- Verify proactive notifications appear in HUD rather than macOS banner alerts.
