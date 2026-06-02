# Walkthrough — Phase Set 7: Native SwiftUI App & Coordinated Daemon Lifecycle

## Summary

Migrated F.R.I.D.A.Y.'s user interface layer from the legacy SwiftBar plugin scripts to a fully custom, standalone native macOS SwiftUI application (`FridayUI`). The application functions as a premium Siri replacement, integrating global option+space hotkeys, physical haptic trackpad feedback, and a procedurally animated volumetric visualizer orb, alongside fully automated backend daemon lifecycle coordination and native macOS permissions prompts.

---

## Changes Made

### Phase 7A — Standalone SwiftUI popover view

**New files:**

| File | Purpose |
|------|---------|
| [FridayUIApp.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/App/FridayUIApp.swift) | Main application lifecycle config. Instantiates the global state objects, handles startup lifecycles, and binds the native macOS `AppDelegate` adapter. |
| [MenuDropdownView.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/Views/MenuDropdownView.swift) | Interactive SwiftUI status menu popover displaying connection matrices, live telemetry, and protected voice execution triggers. |
| [GlowingOrbView.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/Views/GlowingOrbView.swift) | Procedural, hardware-accelerated glowing circle visualizer. Uses SwiftUI rendering, animating radial gradients, high-frequency rotations, and volumetric depth. |
| [FloatingHUDWindow.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/Views/FloatingHUDWindow.swift) | Transparent borderless `NSPanel` floating window positioned directly beneath the macOS menu bar to host the orbital visualizer. |

---

### Phase 7B — Coordinated Daemon Lifecycle Management

**New file:** [DaemonManager.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/Core/DaemonManager.swift)
* Spawns the background Python daemon process utilizing the macOS `Process` API.
* Redirects stdout and stderr streams to rotating log files under `logs/daemon_stdout.log` and `logs/daemon_stderr.log`.
* Integrates a native macOS `AppDelegate` adapter inside the Swift application class (`FridayUIApp.swift`) to intercept app termination signals (like `Cmd + Q`, developer stops, and system shut downs) and gracefully stop the Python daemon to prevent orphaned background processes.

---

### Phase 7C — macOS Entitlements & Permissions Setup

**New files/modifications:**
* [project.pbxproj](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/FridayUI.xcodeproj/project.pbxproj) — Injected native `NSMicrophoneUsageDescription` and `NSCameraUsageDescription` keys and disabled **Hardened Runtime** (`ENABLE_HARDENED_RUNTIME = NO`) locally.
* [MenuDropdownView.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/Views/MenuDropdownView.swift) — Imported `AVFoundation` and called `AVCaptureDevice.requestAccess` for both audio and video on view mount.
* **Result:** macOS now correctly displays the native permission prompts on the user's screen (*"FridayUI would like to access the microphone/camera"*), unblocking the audio streams inside spawned Python subprocesses.

---

### Phase 7D — Legacy Overlay Bypass

**Modified files:**
* [DaemonManager.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/Core/DaemonManager.swift) — Injects the `FRIDAY_NO_OVERLAY = 1` environment variable when spawning the subprocess.
* [activation_handler.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/activation_handler.py) — Bypasses the legacy Tkinter visualizer overlay initialization if the environment variable is active.
* **Result:** The legacy Tkinter circular visualizer is fully bypassed. The annoying "Python rocket/helper" Dock launcher icon no longer appears on startup!

---

### Phase 7E — Optimized IPC Command Queues

**Modified file:** [ipc_bridge.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/ipc_bridge.py)
* Refactored the `toggle_listening` command handler to call `self.handler._queue_wake_word()` directly.
* **Result:** Fully deprecated legacy `SIGUSR1` signalling triggers in favor of fast, clean IPC command queues.

---

### Phase 7F — App Icon Assets

**Staged files:**
* Staged and configured the user's custom logo images (`friday-logo-*.png`) ranging from `16x16` to `1024x1024` pixels inside the Xcode Assets catalog `AppIcon.appiconset`, rendering the F.R.I.D.A.Y. emblem natively in the Mac's Dock.

---

## Testing

* **101 automated unit and integration tests successfully pass** (9.07s) under the optimized IPC queue structure:
  ```bash
  make test
  ```
* Verified that launching `FridayUI` from Xcode successfully:
  * Triggers the native macOS microphone and camera permission prompts.
  * Auto-starts the background Python core process (connecting with status **Green / Core: Active**).
  * Automatically terminates the backend process on application quit cleanly.
