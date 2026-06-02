import SwiftUI

struct MenuDropdownView: View {
    @ObservedObject var ipc: IPCBridge
    
    var body: some View {
        VStack {
            Text("F.R.I.D.A.Y.")
                .font(.headline)
            
            Text("Status: \(ipc.state.uppercased())")
                .foregroundColor(ipc.state == "offline" ? .red : .green)
            
            Text("RAM Buffer: \(String(format: "%.1f", ipc.rssMB)) MB")
                
            Divider()
            
            Button("Activate / Wake Word") {
                ipc.sendCommand("toggle_listening")
            }
            
            Button("Clear Conversation") {
                ipc.sendCommand("clear_history")
            }
            
            Divider()
            
            Button("Shutdown Core") {
                ipc.sendCommand("stop")
            }
            
            Button("Quit UI App") {
                NSApplication.shared.terminate(nil)
            }
        }
        .padding()
        .frame(width: 200)
    }
}
