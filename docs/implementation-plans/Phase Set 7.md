# Implementation Plan — Phase Set 7: Native SwiftUI App & Coordinated Daemon Lifecycle

This plan details the migration of F.R.I.D.A.Y.'s user interface layer from the legacy SwiftBar plugin script to a fully custom, standalone native macOS SwiftUI application (`FridayUI`). The native app functions as a premium Siri replacement, integrating global hotkeys, physical haptic trackpad feedback, and a procedurally animated volumetric visualizer orb, alongside fully automated backend daemon lifecycle coordination.

---

## User Review Required

> [!IMPORTANT]
> - **Deprecation of legacy SwiftBar script**: Cleanly deletes the `swift-daemon/` directory and transitions officially to `FridayUI` as the standard production UI.
> - **Automated Daemon Lifecycle (Coordinated App Launch & Exit)**: The SwiftUI application automatically boots the background Python daemon on app startup, and halts it gracefully on app termination using native macOS `AppDelegate` hooks.
> - **AVFoundation System Permissions**: On first launch, the SwiftUI app explicitly triggers native macOS Microphone and Camera permission prompt popups, eliminating silent OS permission blocks inside spawned Python subprocesses.
> - **Hardened Runtime Entitlement Adjustment**: Disables Hardened Runtime (`ENABLE_HARDENED_RUNTIME = NO`) in the Xcode project build settings for local development to ensure macOS unblocks native permission overlays cleanly.
> - **Legacy Visualizer Bypass (`FRIDAY_NO_OVERLAY`)**: Integrates environment variable injection to bypass the legacy Python/Tkinter circular overlay when running under the native Swift application, preventing the "rocket" Python helper launcher icon from cluttering the macOS Dock.

---

## Proposed Changes

### Component 1: Native SwiftUI Interface (FridayUI)

#### [NEW] [FridayUIApp.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/App/FridayUIApp.swift)
* Set up the SwiftUI App entry point and declare the native macOS `AppDelegate` adaptor.
* Automatically start the daemon on application `.onAppear`, link the daemon to the `AppDelegate`, and register the global option+space hotkey trigger.

#### [NEW] [MenuDropdownView.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/Views/MenuDropdownView.swift)
* Implement a highly polished, interactive SwiftUI status popover displaying system telemetry, active RAM buffer metrics, and connection indicators.
* Import `AVFoundation` and call `AVCaptureDevice.requestAccess` for both audio and video on view mount to trigger macOS system permission prompts.
* Connect the **Quit UI App** action to first cleanly halt the backend daemon prior to terminating the host application.

#### [NEW] [GlowingOrbView.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/Views/GlowingOrbView.swift)
* Build the premium hardware-accelerated circular visualizer in native SwiftUI. Utilizes procedural layers (halos, smoked glass coronas, high-frequency rotating dashed optical braids, and neon gradient cores) modulated by voice telemetry.

#### [NEW] [FloatingHUDWindow.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/Views/FloatingHUDWindow.swift)
* Design a borderless, transparent, non-activating `NSPanel` floating window positioned under the macOS menu bar to host the `GlowingOrbView`.

---

### Component 2: Swift App Core Logic

#### [NEW] [DaemonManager.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/Core/DaemonManager.swift)
* Spawns the background Python daemon process utilizing the macOS `Process` API.
* Redirects stdout and stderr streams to rotating log files under `logs/daemon_stdout.log` and `logs/daemon_stderr.log`.
* Injects the `FRIDAY_NO_OVERLAY = 1` environment variable when spawning the subprocess to instruct Python to deactivate its legacy Tkinter GUI window.

#### [NEW] [IPCBridge.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/Core/IPCBridge.swift)
* Reads and parses `~/.cache/friday/status.json` every 0.1 seconds, driving UI transitions and triggering MacBook trackpad haptics via `NSHapticFeedbackManager` during voice activations.
* Writes `.cmd` commands to `~/.cache/friday/commands/` to trigger manual wake triggers.

#### [NEW] [GlobalHotkeyManager.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/Core/GlobalHotkeyManager.swift)
* Establishes Cocoa local and global monitors to capture and handle the **Option + Space** system hotkey.

#### [NEW] [SystemContextReader.swift](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/Core/SystemContextReader.swift)
* Queries the macOS Accessibility API tree (`AXUIElement`) to gather context from the active foreground window.

---

### Component 3: Python Core & IPC Improvements

#### [MODIFY] [activation_handler.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/activation_handler.py)
* Add a check for `os.getenv("FRIDAY_NO_OVERLAY") == "1"` during startup to skip initializing and running the legacy Tkinter visualizer overlay.

#### [MODIFY] [ipc_bridge.py](file:///Users/khatuaryan/PycharmProjects/Friday/src/core/ipc_bridge.py)
* Refactor the `toggle_listening` command handler to call `self.handler._queue_wake_word()` directly. This replaces the old method of sending a C-style Carbon `SIGUSR1` signal to toggle wake states.

---

### Component 4: Xcode Project Configurations

#### [MODIFY] [project.pbxproj](file:///Users/khatuaryan/PycharmProjects/Friday/FridayUI/FridayUI.xcodeproj/project.pbxproj)
* Add `INFOPLIST_KEY_NSMicrophoneUsageDescription` and `INFOPLIST_KEY_NSCameraUsageDescription` keys containing descriptive permission justifications.
* Set `ENABLE_HARDENED_RUNTIME = NO` for Debug and Release targets to ensure macOS allows local permission prompts.

---

## Verification Plan

### Automated Tests
* Verify all 101 unit tests continue to pass after refactoring Python IPC triggers:
  ```bash
  make test
  ```

### Manual Verification
1. Open the project in Xcode, clean the build folder (`Cmd + Shift + K`), and compile and run the application (`Cmd + R`).
2. Verify that macOS displays the permission prompts: **"FridayUI would like to access the microphone"** and **"FridayUI would like to access the camera"**. Click **Allow** on both.
3. Click the menu bar icon and verify the F.R.I.D.A.Y. status popover appears, showing a green circle and status **"Core: Active"**.
4. Confirm in your Dock that the Python launcher (rocket icon) is **not** displayed.
5. Press `Option + Space` (or speak "Hey Mycroft") and confirm that the floating orb visualizer appears, pulses with your voice, and speaks back a conversational response.
6. Quit the Swift application and verify in Activity Monitor (or `ps aux`) that the background Python daemon process is terminated cleanly.
