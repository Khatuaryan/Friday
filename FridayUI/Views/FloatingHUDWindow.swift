import SwiftUI
import AppKit

struct FloatingHUDWindow: View {
    @ObservedObject var ipc: IPCBridge
    
    var body: some View {
        VStack {
            // Draw visualizer only when the core assistant is active
            if ipc.state != "offline" && ipc.state != "idle" {
                GlowingOrbView(ipc: ipc)
                    .transition(.opacity.combined(with: .scale))
                    .onTapGesture {
                        // Let the boss trigger listening by clicking directly on the orb
                        ipc.sendCommand("toggle_listening")
                    }
            }
        }
        .onAppear {
            configureAppKitWindow()
        }
    }
    
    /// Directly configures the window layer to have borderless and transparent styles
    private func configureAppKitWindow() {
        // Retrieve standard window handler
        guard let window = NSApplication.shared.windows.first(where: { $0.title == "FridayUI" }) else { return }
        
        // Remove standard borders, make background transparent
        window.backgroundColor = .clear
        window.isOpaque = false
        window.hasShadow = false
        window.styleMask = [.borderless]
        
        // Layering overlays: float above all applications and on full screen views
        window.level = .statusBar
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        
        // Place in top-right area, directly underneath the macOS status bar
        if let screen = NSScreen.main {
            let screenFrame = screen.visibleFrame
            let size: CGFloat = 160
            let x = screenFrame.maxX - size - 16
            let y = screenFrame.maxY - size - 16
            window.setFrame(NSRect(x: x, y: y, width: size, height: size), display: true)
        }
    }
}
