import SwiftUI
import AVFoundation

struct MenuDropdownView: View {
    @ObservedObject var ipc: IPCBridge
    @ObservedObject var daemon: DaemonManager // Passed from FridayUIApp for coordinated lifecycle
    
    var body: some View {
        VStack(spacing: 12) {
            Text("F.R.I.D.A.Y.")
                .font(.headline)
                .fontWeight(.bold)
            
            // Core Connection Status Indicator
            HStack(spacing: 6) {
                Circle()
                    .fill(daemon.isRunning ? Color.green : Color.red)
                    .frame(width: 8, height: 8)
                Text(daemon.isRunning ? "Core: Active" : "Core: Offline")
                    .font(.subheadline)
            }
            
            Text("State: \(ipc.state.uppercased())")
                .font(.caption)
                .foregroundColor(ipc.state == "listening" ? .cyan : (ipc.state == "speaking" ? .pink : .secondary))
            
            Text("RAM Buffer: \(String(format: "%.1f", ipc.rssMB)) MB")
                .font(.caption)
                .foregroundColor(.secondary)
                
            Divider()
            
            // Note: Boot Core / Stop Core is now fully automated in the app lifecycle!
            
            Button("Activate / Wake Word") {
                ipc.sendCommand("toggle_listening")
            }
            .frame(maxWidth: .infinity)
            .buttonStyle(.bordered)
            .disabled(!daemon.isRunning)
            
            Button("Clear Conversation") {
                ipc.sendCommand("clear_history")
            }
            .frame(maxWidth: .infinity)
            .buttonStyle(.bordered)
            .disabled(!daemon.isRunning)
            
            Divider()
            
            Button("Quit UI App") {
                daemon.stopDaemon() // Cleanly stop the daemon first
                NSApplication.shared.terminate(nil)
            }
            .frame(maxWidth: .infinity)
            .buttonStyle(.plain)
            .foregroundColor(.secondary)
        }
        .padding()
        .frame(width: 220)
        .onAppear {
            daemon.checkStatus()
        }
    }
}


