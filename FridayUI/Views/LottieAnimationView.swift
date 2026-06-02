import SwiftUI
import Lottie

struct LottiePlayerView: NSViewRepresentable {
    let animationName: String   // e.g. "listening", "thinking", "responding"
    var loopMode: LottieLoopMode = .loop
    
    func makeNSView(context: Context) -> LottieAnimationView {
        let view = LottieAnimationView(name: animationName, bundle: .main)
        view.loopMode = loopMode
        view.contentMode = .scaleAspectFit
        view.backgroundBehavior = .pauseAndRestore
        view.play()
        return view
    }
    
    func updateNSView(_ nsView: LottieAnimationView, context: Context) {
        // If the animation name changed (state transition), swap the animation
        if nsView.animation?.name != animationName {
            nsView.animation = LottieAnimation.named(animationName, bundle: .main)
            nsView.play()
        }
    }
}
