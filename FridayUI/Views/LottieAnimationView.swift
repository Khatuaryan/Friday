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
        // If the animation name changed (state transition), swap the animation
        if context.coordinator.currentAnimationName != animationName {
            context.coordinator.currentAnimationName = animationName
            nsView.animation = LottieAnimation.named(animationName, bundle: .main)
            nsView.play()
        }
    }
}
