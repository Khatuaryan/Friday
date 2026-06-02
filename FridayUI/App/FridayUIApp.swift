import SwiftUI

class AppDelegate: NSObject, NSApplicationDelegate {
    var daemon: DaemonManager?
    
    func applicationWillTerminate(_ notification: Notification) {
        print("Application terminating — cleanly stopping F.R.I.D.A.Y. daemon...")
        daemon?.stopDaemon()
    }
}

@main
struct FridayUIApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var ipc = IPCBridge()
    @StateObject private var daemon = DaemonManager()
    @State private var isHUDShowing = true
    
    var body: some Scene {
        // 1. Status menu bar item and dropdown
        MenuBarExtra {
            MenuDropdownView(ipc: ipc, daemon: daemon)
                .onAppear {
                    // Link daemon to AppDelegate for clean app termination handling
                    appDelegate.daemon = daemon
                    
                    // Automatically boot the Python core on launch!
                    daemon.startDaemon()
                    
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
        .menuBarExtraStyle(.window) // Configures the menu bar popover as an interactive SwiftUI view
        
        // 2. Floating Siri HUD visualizer
        WindowGroup {
            FloatingHUDWindow(ipc: ipc)
        }
        .windowStyle(.hiddenTitleBar)
    }
}



