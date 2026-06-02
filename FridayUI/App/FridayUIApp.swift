import SwiftUI

@main
struct FridayUIApp: App {
    @StateObject private var ipc = IPCBridge()
    @State private var isHUDShowing = true
    
    var body: some Scene {
        // 1. Status menu bar item and dropdown
        MenuBarExtra {
            MenuDropdownView(ipc: ipc)
                .onAppear {
                    // Register hotkey when menu dropdown mounts
                    GlobalHotkeyManager.shared.register {
                        ipc.sendCommand("toggle_listening")
                    }
                }
        } label: {
            HStack {
                Image("friday-icon-menubar")
                if ipc.state == "listening" {
                    Text("•")
                }
            }
        }
        
        // 2. Floating Siri HUD visualizer
        WindowGroup {
            FloatingHUDWindow(ipc: ipc)
        }
        .windowStyle(.hiddenTitleBar)
    }
}
