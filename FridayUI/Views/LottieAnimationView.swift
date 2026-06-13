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

        // Layer-backed transparency
        view.wantsLayer = true
        view.layer?.backgroundColor = NSColor.clear.cgColor

        // CRITICAL FIX: Disable layer clipping so glow/bloom effects on outer
        // ring and calibration chassis elements are not cut at the NSView frame
        // boundary. The parent panel (240x320) has sufficient space for overflow.
        // masksToBounds = false is the macOS equivalent of iOS clipsToBounds = false.
        // This must be set AFTER wantsLayer = true (layer is created at that point).
        view.layer?.masksToBounds = false

        view.play()
        context.coordinator.currentAnimationName = animationName
        return view
    }

    func updateNSView(_ nsView: LottieAnimationView, context: Context) {
        // Swap animation on state transition
        if context.coordinator.currentAnimationName != animationName {
            context.coordinator.currentAnimationName = animationName
            nsView.animation = LottieAnimation.named(animationName, bundle: .main)
            nsView.loopMode = loopMode
            nsView.play()
        }
        // Sync loopMode changes that don't require a name change
        if nsView.loopMode != loopMode {
            nsView.loopMode = loopMode
        }
    }
}
