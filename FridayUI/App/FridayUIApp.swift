import SwiftUI

@main
struct FridayUIApp: App {
    @StateObject private var ipc = IPCBridge()
    @State private var isHUDShowing = false
    
    var body: some Scene {
        // 1. Native SwiftUI Menu Bar dropdown (Replaces SwiftBar)
        MenuBarExtra {
            MenuDropdownView(ipc: ipc)
        } label: {
            HStack {
                Image("friday-icon-menubar") // Load 22x22 PNG asset
                if ipc.state == "listening" {
                    Text("•") // Micro-status pulse
                }
            }
        }
        
        // 2. Floating Siri-like overlay window
        WindowGroup {
            if isHUDShowing {
                FloatingHUDWindow(ipc: ipc)
            }
        }
        
        .windowStyle(.hiddenTitleBar)
    }
    // Inside FridayUIApp.swift
    .onAppear {
        GlobalHotkeyManager.shared.register {
            ipc.sendCommand("toggle_listening")
        }
    }

}
