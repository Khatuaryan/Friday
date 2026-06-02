import SwiftUI

struct ResponseBubbleView: View {
    let command: String
    let response: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if !command.isEmpty {
                HStack(alignment: .top, spacing: 6) {
                    Text("👤")
                        .font(.system(size: 11))
                    VStack(alignment: .leading, spacing: 2) {
                        Text("You")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(.gray)
                        Text(command)
                            .font(.system(size: 12, weight: .medium))
                            .foregroundColor(.white.opacity(0.85))
                            .lineLimit(2)
                    }
                }
                .transition(.opacity.combined(with: .slide))
            }
            
            if !command.isEmpty && !response.isEmpty {
                Divider()
                    .background(Color.white.opacity(0.15))
            }
            
            if !response.isEmpty {
                HStack(alignment: .top, spacing: 6) {
                    Text("🤖")
                        .font(.system(size: 12))
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Friday")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(Color(hex: "#00F2FF")) // custom cyan J.A.R.V.I.S. color from target
                        Text(response)
                            .font(.system(size: 13, weight: .regular))
                            .foregroundColor(.white)
                            .lineLimit(4)
                    }
                }
                .transition(.opacity.combined(with: .slide))
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 14)
                .fill(Color.black.opacity(0.75))
                .shadow(color: Color.black.opacity(0.3), radius: 10, x: 0, y: 5)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(Color.white.opacity(0.1), lineWidth: 1)
        )
        .padding(.horizontal, 16)
        .transition(.asymmetric(
            insertion: .opacity.combined(with: .move(edge: .bottom)),
            removal: .opacity
        ))
    }
}
