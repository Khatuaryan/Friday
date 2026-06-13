# FridayUI Project Summary

## Project Aim

FridayUI is a macOS SwiftUI menu-bar companion app for F.R.I.D.A.Y., a Python-based assistant core located outside this Xcode project at `~/PycharmProjects/Friday`. The UI app is responsible for launching and stopping the Python daemon, showing assistant status in the macOS menu bar, exposing manual controls, registering a global wake hotkey, and rendering a floating always-on-top visual HUD while the assistant listens, processes, or speaks.

The project is not the full assistant brain. It is the native macOS shell around the Python core. Communication between the Swift app and Python daemon is file-based IPC under `~/.cache/friday`.

## High-Level Architecture

The app has three main layers:

1. App lifecycle and windows: `FridayUIApp` creates the menu bar item and a separate floating HUD window.
2. Core services: `DaemonManager`, `IPCBridge`, `GlobalHotkeyManager`, and `SystemContextReader` manage daemon lifecycle, file IPC, global keyboard activation, and optional active-window context collection.
3. Views: SwiftUI/AppKit bridge views render the menu dropdown, floating HUD, Lottie animations, fallback glowing orb, and command/response bubble.

The bundled `Lottie/` directory is the Lottie package source used to play JSON animations. The FridayUI app depends on it, but it is third-party/library code rather than core app logic.

## Runtime Workflow

1. The user launches FridayUI.
2. `FridayUIApp` creates a `MenuBarExtra` and a hidden-title-bar `WindowGroup` for the floating HUD.
3. When the menu dropdown appears, the app links the `DaemonManager` into `AppDelegate`, starts the Python daemon, and registers Option + Space as the global hotkey.
4. `DaemonManager` starts `~/PycharmProjects/Friday/.venv/bin/python -m src.core` with working directory `~/PycharmProjects/Friday`.
5. The Python daemon is expected to write status to `~/.cache/friday/status.json` and maintain a PID file at `~/.cache/friday/friday.pid`.
6. `IPCBridge` polls `status.json` every 0.1 seconds and publishes state, memory, last command, and last response to SwiftUI.
7. User actions such as menu button clicks, HUD taps, or Option + Space create command files like `~/.cache/friday/commands/toggle_listening.cmd`.
8. The Python daemon is expected to consume those command files and update `status.json`.
9. The HUD maps assistant states to animations:
   - `verifying` / `ready` -> `listening.json`
   - `processing` -> `thinking.json`
   - `speaking` -> `responding.json`
   - any other state -> hidden HUD content
10. On app termination, `AppDelegate` calls `daemon.stopDaemon()` for a clean daemon shutdown.

## File-by-File Summary

### `FridayUI/App/FridayUIApp.swift`

Main app entry point. Defines `AppDelegate` for termination cleanup and `FridayUIApp` as the SwiftUI `@main` app. Owns shared `IPCBridge` and `DaemonManager` instances. Builds the menu bar extra, starts the daemon on menu appearance, registers Option + Space to send `toggle_listening`, and creates the floating HUD window.

Important behavior:

- Starts the Python daemon automatically.
- Stops the daemon on app termination.
- Uses `Image("friday-icon-menubar")` for the menu bar icon.
- Shows a dot in the menu bar while `ipc.state == "listening"`.

### `FridayUI/App/ContentView.swift`

A standalone diagnostics/control view showing the app title, daemon status, telemetry state, memory footprint, RAM pressure, and buttons to boot/stop the core or trigger voice activation.

Current note: this view does not appear to be wired into the active app scene. The current app uses `MenuDropdownView` and `FloatingHUDWindow` instead. It may be older UI, a debugging view, or leftover code.

Potential issue: it loads an icon using an absolute path: `/Users/khatuaryan/PycharmProjects/Friday/assets/friday-icon.png`. That will fail on another machine or if the sibling project moves.

### `FridayUI/App/animations/listening.json`

Bundled Lottie animation used when the assistant is in `verifying` or `ready` state. Loaded by name from the main bundle.

### `FridayUI/App/animations/thinking.json`

Bundled Lottie animation used when the assistant is in `processing` state.

### `FridayUI/App/animations/responding.json`

Bundled Lottie animation used when the assistant is in `speaking` state.

### `FridayUI/App/Assets.xcassets`

Asset catalog for app images and colors. The app expects at least `friday-icon-menubar` to exist here because `FridayUIApp` references it by asset name.

### `FridayUI/Core/DaemonManager.swift`

Observable service that manages the Python assistant daemon.

Responsibilities:

- Tracks `isRunning` for SwiftUI.
- Reads `~/.cache/friday/friday.pid` and checks process liveness with `kill(pid, 0)`.
- Starts the Python daemon using `Process`.
- Uses `~/PycharmProjects/Friday` as the working directory.
- Runs `.venv/bin/python -m src.core`.
- Sets `FRIDAY_NO_OVERLAY=1` to disable the old Python/Tkinter overlay because the native Swift UI is now responsible for visuals.
- Redirects daemon stdout/stderr to `~/PycharmProjects/Friday/logs/daemon_stdout.log` and `daemon_stderr.log`.
- Stops the daemon with SIGTERM using the PID file and also terminates the locally stored `Process` if present.

Potential issues:

- The path to the Python project is hard-coded to `~/PycharmProjects/Friday`.
- `startDaemon()` calls `checkStatus()` and immediately checks `isRunning`, but `checkStatus()` updates asynchronously on the main queue. This can make the guard depend on stale state.
- The app trusts the PID file. A stale PID file pointing to an unrelated process could be risky.
- File handles opened for logging are not explicitly closed.
- The file imports Combine even though project guidance prefers async/await where practical. SwiftUI `ObservableObject` still commonly uses Combine-backed publishing.

### `FridayUI/Core/IPCBridge.swift`

Observable service that implements file-based IPC with the Python daemon.

Responsibilities:

- Publishes assistant state, memory pressure, RSS memory, last command, and last response.
- Polls `~/.cache/friday/status.json` every 0.1 seconds.
- Creates `~/.cache/friday/commands` if missing.
- Parses JSON status values using `JSONSerialization`.
- Sends commands by creating empty `.cmd` files, for example `toggle_listening.cmd` or `clear_history.cmd`.
- Triggers haptic feedback when state transitions into `listening`.

Expected `status.json` fields:

- `state`: string, such as `offline`, `ready`, `verifying`, `listening`, `processing`, or `speaking`.
- `rss_mb`: number.
- `pressure`: string.
- `last_command`: string.
- `last_response`: string.

Potential issues:

- Polling every 0.1 seconds is simple but relatively aggressive for file IO.
- `JSONSerialization` with `[String: Any]` is flexible but weakly typed. A `Codable` status model would be safer.
- The timer is not invalidated in `deinit`.
- Command files are empty; command semantics rely entirely on filename conventions shared with the Python core.

### `FridayUI/Core/GlobalHotkeyManager.swift`

Singleton that registers Option + Space as the activation hotkey.

Responsibilities:

- Stores a trigger closure.
- Adds a global key-down monitor for background app activation.
- Adds a local key-down monitor for foreground activation.
- Swallows the local Option + Space event so active text fields do not receive a space.

Potential issues:

- Event monitors are not stored, so they cannot be removed later.
- Calling `register` more than once can install duplicate monitors.
- `NSEvent.addGlobalMonitorForEvents` may require Accessibility permissions for reliable global keyboard monitoring depending on macOS privacy settings and context.
- This is not a Carbon hotkey registration, so behavior may differ from a true system hotkey.

### `FridayUI/Core/SystemContextReader.swift`

Utility for reading frontmost app context through macOS Accessibility APIs.

Responsibilities:

- Reads the frontmost application name and bundle ID.
- Attempts to read the focused window title.
- Attempts to read selected text from the focused window.

Current note: this file is not referenced by the visible app flow in the current Swift files. It may be intended for future context injection into assistant requests.

Potential issues:

- Requires Accessibility permissions.
- `kAXSelectedTextAttribute` is usually an attribute of focused text elements, not necessarily the focused window itself, so selected-text capture may fail for many apps.
- The cast `focusedWindow as! AXUIElement?` is forceful and could be made safer.

### `FridayUI/Views/FloatingHUDWindow.swift`

SwiftUI view for the floating assistant HUD.

Responsibilities:

- Observes `IPCBridge` state.
- Maps assistant states to Lottie animation names.
- Shows a Lottie animation if the corresponding JSON file exists in the app bundle.
- Falls back to `GlowingOrbView` if the animation file is missing.
- Shows `ResponseBubbleView` when there is a last command or response.
- Sends `toggle_listening` when the HUD is tapped.
- Uses `WindowConfigurator` to access and configure the underlying `NSWindow`.

Window behavior:

- Transparent background.
- Borderless style.
- No shadow.
- Window level `.statusBar`.
- Joins all spaces and full-screen spaces.
- Positioned near the top-right of the main screen.
- Ordered front regardless of active app.

Potential issues:

- Reconfiguring the AppKit window in `updateNSView` may repeatedly reset frame/style.
- Fixed window size and position may not adapt well to screen changes, multiple displays, or menu bar/notch layouts.
- `isHUDShowing` exists in `FridayUIApp` but is not currently used to control this window.

### `FridayUI/Views/LottieAnimationView.swift`

Bridge from SwiftUI to Lottie's AppKit `LottieAnimationView` using `NSViewRepresentable`.

Responsibilities:

- Creates a Lottie animation view from a bundled animation name.
- Sets loop mode, scale aspect fit, and pause/restore background behavior.
- Tracks the current animation name in a coordinator.
- Swaps and plays a new animation when SwiftUI state changes.

Potential issue: if `loopMode` changes while the animation name stays the same, `updateNSView` does not currently update `nsView.loopMode`.

### `FridayUI/Views/GlowingOrbView.swift`

Fallback SwiftUI animation used when Lottie JSON files are unavailable.

Responsibilities:

- Draws a pulsing multi-layer orb with radial gradients and dashed rotating rings.
- Changes colors based on `ipc.state`:
  - `listening`: cyan.
  - `processing`: purple.
  - `speaking`: pink.
  - default: cyan.
- Adds a `Color(hex:)` extension used here and by `ResponseBubbleView`.

Potential issue: the animation uses `phase` with a repeating animation toward a fixed value. Since the body computes `sin(phase)`, the pulsing may not behave like a continuously advancing oscillator in all SwiftUI update scenarios.

### `FridayUI/Views/MenuDropdownView.swift`

Menu-bar dropdown UI.

Responsibilities:

- Displays app title.
- Displays daemon running/offline state.
- Displays assistant state and RAM usage from IPC.
- Provides `Activate / Wake Word`, which sends `toggle_listening`.
- Provides `Clear Conversation`, which sends `clear_history`.
- Provides `Quit UI App`, which stops the daemon and terminates the app.
- Requests microphone and camera permissions on appear.

Potential issues:

- Camera permission is requested even though this Swift UI code does not appear to use camera input directly.
- Permission prompts happen from menu appearance, which can feel surprising if the user only opens the menu.
- The controls are disabled based on `daemon.isRunning`, but IPC may still be offline if the daemon is alive but not publishing status.

### `FridayUI/Views/ResponseBubbleView.swift`

Small HUD bubble for recent user command and assistant response.

Responsibilities:

- Shows a user section when `command` is not empty.
- Shows an assistant section when `response` is not empty.
- Adds a divider when both exist.
- Uses a dark rounded background, subtle stroke, and fixed line limits.

Potential issues:

- Uses emoji icons, which may render differently across macOS versions and fonts.
- Long commands and responses are truncated with line limits instead of expandable detail.

### `FridayUI/Products/FridayUI.app`

Build product generated by Xcode. This is the compiled macOS app bundle, not source code.

### `FridayUI/Products/FridayUITests.xctest`

Build product for unit tests. The actual test source files are not shown in the provided project structure.

### `FridayUI/Products/FridayUIUITests.xctest`

Build product for UI tests. The actual UI test source files are not shown in the provided project structure.

## `Lottie/` Directory

The `Lottie/` directory is a full local copy of the Lottie package. FridayUI imports `Lottie` in `LottieAnimationView.swift` and uses it to render the assistant state animations.

Important contents:

- `Lottie/Package.swift`: Swift Package Manager manifest for Lottie.
- `Lottie/README.md`: Lottie documentation.
- `Lottie/Sources/...`: Lottie implementation source code.
- `Lottie/Example/...`: Example app code provided by Lottie.
- `Lottie/script/...`: Release/test/support scripts and sample projects.
- `Lottie/_AeFiles/...`: After Effects project files used by the Lottie project.
- `Lottie/_Gifs/...`: README/example visual assets.

This folder is dependency/vendor code. It should usually be left untouched unless upgrading or patching Lottie itself.

## How The App Works With The Python Core

FridayUI and the Python core communicate through a small file protocol:

- Swift starts Python by running `.venv/bin/python -m src.core` in `~/PycharmProjects/Friday`.
- Python writes its PID to `~/.cache/friday/friday.pid`.
- Python writes live state to `~/.cache/friday/status.json`.
- Swift polls that status file and updates UI.
- Swift sends commands by writing empty files into `~/.cache/friday/commands`.
- Python watches or polls the commands directory and reacts to command filenames.

This approach is easy to debug because all state is visible in the filesystem. The tradeoff is that it depends heavily on path conventions, polling frequency, and both sides agreeing on JSON keys and command filenames.

## Current Assistant States In The UI

The UI recognizes these state strings directly:

- `offline`: no status file found or IPC unavailable.
- `listening`: menu bar dot appears, haptic feedback triggers on entry, state text becomes cyan.
- `verifying`: HUD shows listening animation.
- `ready`: HUD shows listening animation.
- `processing`: HUD shows thinking animation/orb color.
- `speaking`: HUD shows responding animation/orb color, state text becomes pink.

There may be additional daemon states not represented in the Swift UI. Unknown states hide the HUD animation because `animationNameForState` returns `nil`.

## Known Problems And Risks

- Hard-coded local paths make the app machine-specific.
- The Swift app depends on a sibling Python project that is not part of this Xcode target.
- Daemon lifecycle checks are based on a PID file and asynchronous `isRunning` updates.
- File IPC is simple but can be brittle under partial writes, stale files, or rapid state changes.
- Status parsing is untyped and does not validate schema.
- Global hotkey monitors are never removed and may duplicate if registered repeatedly.
- Accessibility, microphone, and camera permissions may be required or requested, but the user-facing permission story is not centralized.
- `ContentView` and `SystemContextReader` appear unused in the active app flow.
- The floating HUD has fixed sizing and positioning.
- There is no visible test source in the provided structure, only test products.
- The app imports Combine in observable services, despite the stated preference to avoid Combine where async APIs are a practical fit.

## Development Workflow

Typical local workflow:

1. Open the FridayUI Xcode project.
2. Ensure the Python core exists at `~/PycharmProjects/Friday`.
3. Ensure the Python virtual environment exists at `~/PycharmProjects/Friday/.venv/bin/python`.
4. Ensure the Python module can run with `python -m src.core`.
5. Build and run FridayUI from Xcode.
6. Open the menu bar item to trigger daemon startup if it has not already happened.
7. Use Option + Space, the menu button, or HUD tap to send `toggle_listening`.
8. Check `~/.cache/friday/status.json` for live daemon state.
9. Check `~/PycharmProjects/Friday/logs/daemon_stdout.log` and `daemon_stderr.log` for Python daemon logs.

## Recommended Cleanup / Next Improvements

1. Replace hard-coded paths with configurable settings or bundled defaults.
2. Introduce a typed `Codable` model for `status.json`.
3. Make daemon status checks synchronous or return values directly to avoid stale `isRunning` guards.
4. Store and remove hotkey event monitors.
5. Decide whether `ContentView` is still needed; remove it or wire it into a debug window.
6. Decide whether `SystemContextReader` is part of the product; if yes, make Accessibility permission handling explicit.
7. Revisit camera permission request unless the Python core actually requires camera access from the UI app.
8. Add focused tests for status parsing, command creation, and daemon path handling.
9. Make HUD placement adaptive for multiple displays and screen changes.
10. Consider replacing polling file IPC with a more robust local mechanism if latency or reliability becomes a problem, such as XPC, local sockets, or Darwin notifications paired with files.
