import SwiftUI

struct GlowingOrbView: View {
    @ObservedObject var ipc: IPCBridge
    @State private var phase = 0.0
    @State private var rotation = 0.0
    
    // Colors matching our spec profiles
    private var coreColor: Color {
        switch ipc.state {
        case "listening": return Color(hex: "#00F2FF")
        case "processing": return Color(hex: "#BF00FF")
        case "speaking": return Color(hex: "#FF007F")
        default: return Color(hex: "#00F2FF")
        }
    }
    
    private var coronaColor: Color {
        switch ipc.state {
        case "listening": return Color(hex: "#006688")
        case "processing": return Color(hex: "#550077")
        case "speaking": return Color(hex: "#880033")
        default: return Color(hex: "#006688")
        }
    }

    var body: some View {
        let pulseScale1: CGFloat = CGFloat(1.0 + 0.15 * sin(phase))
        let pulseScale2: CGFloat = CGFloat(0.95 + 0.05 * sin(phase + 1.0))
        let pulseScale3: CGFloat = CGFloat(0.85 + 0.07 * sin(phase * 1.5))
        
        ZStack {
            // Layer 1: Emissivity Halo
            Circle()
                .fill(RadialGradient(
                    gradient: Gradient(colors: [coronaColor.opacity(0.4), Color.clear]),
                    center: .center, startRadius: 10, endRadius: 70
                ))
                .scaleEffect(pulseScale1)
            
            // Layer 2: Smoked Corona
            Circle()
                .fill(RadialGradient(
                    gradient: Gradient(colors: [coronaColor, Color.black.opacity(0.8)]),
                    center: .center, startRadius: 5, endRadius: 40
                ))
                .scaleEffect(pulseScale2)
            
            // Layer 3: High-Frequency Optical Braids
            ZStack {
                let braidRotation = rotation
                ForEach(0..<4) { i in
                    Circle()
                        .stroke(coreColor.opacity(0.7), style: StrokeStyle(lineWidth: 1.5, dash: [4, 12]))
                        .scaleEffect(CGFloat(0.7 + 0.08 * Double(i)))
                        .rotationEffect(.degrees(braidRotation + Double(i * 45)))
                }
            }
            
            // Layer 4: Hot Neon Core
            Circle()
                .fill(RadialGradient(
                    gradient: Gradient(colors: [.white, coreColor]),
                    center: .center, startRadius: 0, endRadius: 18
                ))
                .scaleEffect(pulseScale3)
        }
        .frame(width: 120, height: 120)
        .onAppear {
            withAnimation(.linear(duration: 4).repeatForever(autoreverses: false)) {
                rotation = 360.0
            }
            withAnimation(.easeInOut(duration: 1.25).repeatForever(autoreverses: true)) {
                phase = .pi * 2
            }
        }
    }
}

// Convenient Hex color initializer
extension Color {
    init(hex: String) {
        let trimmed = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: trimmed).scanHexInt64(&int)
        let r = Double((int >> 16) & 0xff) / 255.0
        let g = Double((int >> 8) & 0xff) / 255.0
        let b = Double(int & 0xff) / 255.0
        self.init(.sRGB, red: r, green: g, blue: b, opacity: 1.0)
    }
}
