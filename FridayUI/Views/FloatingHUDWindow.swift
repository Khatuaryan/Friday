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
        .onChange(of: ipc.state) { oldValue, newValue in
            updateMouseEvents(for: newValue)
        }
        .onAppear {
            updateMouseEvents(for: ipc.state)
        }
    }
    
    private func updateMouseEvents(for state: String) {
        let hasActiveAnimation = (state == "verifying" || state == "ready" || state == "processing" || state == "speaking")
        if let delegate = NSApplication.shared.delegate as? AppDelegate,
           let panel = delegate.hudPanel {
            panel.ignoresMouseEvents = !hasActiveAnimation
        }
    }
}


