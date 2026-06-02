import SwiftUI

struct ContentView: View {
    @StateObject private var daemon = DaemonManager()
    @StateObject private var ipc = IPCBridge()
    
    var body: some View {
        VStack(spacing: 20) {
            // Title Header
            HStack(spacing: 12) {
                Image(nsImage: NSImage(contentsOfFile: "/Users/khatuaryan/PycharmProjects/Friday/assets/friday-icon.png") ?? NSImage())
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .frame(width: 60, height: 60)
                    .clipShape(Circle())
                    .shadow(radius: 3)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text("F.R.I.D.A.Y.")
                        .font(.title3)
                        .fontWeight(.bold)
                    Text("Siri Replacement Status & Controls")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            Divider()
            
            // System Diagnostics Matrix
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Python Core:")
                        .bold()
                        .frame(width: 130, alignment: .leading)
                    HStack(spacing: 6) {
                        Circle()
                            .fill(daemon.isRunning ? Color.green : Color.red)
                            .frame(width: 8, height: 8)
                        Text(daemon.isRunning ? "Active" : "Offline")
                    }
                }
                
                HStack {
                    Text("Telemetry State:")
                        .bold()
                        .frame(width: 130, alignment: .leading)
                    Text(ipc.state.uppercased())
                        .foregroundColor(ipc.state == "listening" ? .cyan : (ipc.state == "speaking" ? .pink : .primary))
                }
                
                HStack {
                    Text("Memory Footprint:")
                        .bold()
                        .frame(width: 130, alignment: .leading)
                    Text("\(String(format: "%.1f", ipc.rssMB)) MB")
                }
                
                HStack {
                    Text("RAM Pressure:")
                        .bold()
                        .frame(width: 130, alignment: .leading)
                    Text(ipc.memoryPressure.uppercased())
                        .foregroundColor(ipc.memoryPressure == "critical" ? .red : .primary)
                }
            }
            .padding(.horizontal, 24)
            
            Divider()
            
            // Console Controllers
            HStack(spacing: 16) {
                Button(action: {
                    if daemon.isRunning {
                        daemon.stopDaemon()
                    } else {
                        daemon.startDaemon()
                    }
                }) {
                    Text(daemon.isRunning ? "Stop Core" : "Boot Core")
                        .bold()
                        .frame(width: 100, height: 20)
                }
                .buttonStyle(.borderedProminent)
                .tint(daemon.isRunning ? .red : .blue)
                
                Button(action: {
                    ipc.sendCommand("toggle_listening")
                }) {
                    Text("Trigger Voice")
                        .frame(width: 100, height: 20)
                }
                .buttonStyle(.bordered)
                .disabled(!daemon.isRunning)
            }
            .padding(.bottom, 8)
        }
        .padding()
        .frame(width: 380, height: 290)
        .onAppear {
            daemon.checkStatus()
        }
    }
}
