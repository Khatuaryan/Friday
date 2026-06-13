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
                    ZStack {
                        if useLottieAnimation(animName) {
                            LottiePlayerView(animationName: animName)
                                // SIZING NOTE: The Lottie composition is 580x580 after the canvas
                                // fix. scaleAspectFit will render the full composition at 120x120.
                                // The .frame here is the LAYOUT frame — it defines how much space
                                // this view claims in the VStack. Glow/bloom effects are allowed to
                                // overflow into the surrounding VStack space (the panel is 240x320,
                                // giving 60px on each side of the 120px-wide animation).
                                // Do NOT add .clipped() here — that would re-introduce the bug.
                                .frame(width: 120, height: 120)
                                .transition(.opacity.combined(with: .scale))
                        } else {
                            GlowingOrbView(ipc: ipc)
                                .frame(width: 120, height: 120)
                                .transition(.opacity.combined(with: .scale))
                        }
                    }
                    // Extra transparent padding around the animation so SwiftUI layout
                    // never clips the overflow glow effects against a sibling view.
                    .padding(20)

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
        .frame(width: 240, height: 320, alignment: .top)
        .onChange(of: ipc.state) { oldValue, newValue in
            updateMouseEvents(for: newValue)
        }
        .onAppear {
            updateMouseEvents(for: ipc.state)
        }
    }

    private func updateMouseEvents(for state: String) {
        let hasActiveAnimation = (state == "verifying" || state == "ready"
                                  || state == "processing" || state == "speaking")
        if let delegate = NSApplication.shared.delegate as? AppDelegate,
           let panel = delegate.hudPanel {
            panel.ignoresMouseEvents = !hasActiveAnimation
        }
    }
}
