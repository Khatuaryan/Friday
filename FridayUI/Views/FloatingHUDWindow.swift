import SwiftUI
import AppKit

struct FloatingHUDWindow: View {
    @ObservedObject var ipc: IPCBridge
    
    private var animationNameForState: String? {
        switch ipc.state {
        case "verifying", "ready":
            return "listening"
        case "processing":
            return "thinking"
        case "speaking":
            return "responding"
        default:
            return nil
        }
    }
    
    private func useLottieAnimation(_ name: String) -> Bool {
        return Bundle.main.path(forResource: name, ofType: "json") != nil
    }
    
    var body: some View {
        VStack(spacing: 0) {
            if let animName = animationNameForState {
                VStack(spacing: 12) {
                    if useLottieAnimation(animName) {
                        LottiePlayerView(animationName: animName)
                            .frame(width: 160, height: 160)
                            .transition(.opacity.combined(with: .scale))
                    } else {
                        GlowingOrbView(ipc: ipc)
                            .transition(.opacity.combined(with: .scale))
                    }
                    
                    if !ipc.lastCommand.isEmpty || !ipc.lastResponse.isEmpty {
                        ResponseBubbleView(command: ipc.lastCommand, response: ipc.lastResponse)
                    }
                }
                .onTapGesture {
                    ipc.sendCommand("toggle_listening")
                }
                .transition(.opacity.combined(with: .slide))
            }
        }
        .frame(width: 280, height: 360, alignment: .top)
        .background(WindowConfigurator { window in
            configureAppKitWindow(window)
        })
    }
    
    /// Directly configures the window layer to have borderless and transparent styles
    private func configureAppKitWindow(_ window: NSWindow) {
        // Remove standard borders, make background transparent
        window.backgroundColor = .clear
        window.isOpaque = false
        window.hasShadow = false
        window.styleMask = [.borderless]
        
        // Layering overlays: float above all applications and on full screen views
        window.level = .statusBar
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle]
        
        // Place in top-right area, directly underneath the macOS status bar
        if let screen = NSScreen.main {
            let screenFrame = screen.visibleFrame
            let width: CGFloat = 280
            let height: CGFloat = 360
            let x = screenFrame.maxX - width - 16
            let y = screenFrame.maxY - height - 16
            window.setFrame(NSRect(x: x, y: y, width: width, height: height), display: true)
        }
        
        // Force the window to be frontmost above all apps and screens
        window.orderFrontRegardless()
    }
}

/// Helper representable to dynamically fetch and configure the AppKit hosting window
struct WindowConfigurator: NSViewRepresentable {
    let configure: (NSWindow) -> Void
    
    func makeNSView(context: Context) -> NSView {
        let view = NSView()
        DispatchQueue.main.async {
            if let window = view.window {
                configure(window)
            }
        }
        return view
    }
    
    func updateNSView(_ nsView: NSView, context: Context) {
        if let window = nsView.window {
            configure(window)
        }
    }
}


