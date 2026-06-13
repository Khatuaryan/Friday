import SwiftUI
import AppKit

class AppDelegate: NSObject, NSApplicationDelegate {
    let ipc = IPCBridge()
    let daemon = DaemonManager()
    var hudPanel: NSPanel?
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        print("Application did finish launching — setting up F.R.I.D.A.Y. HUD and hotkeys...")
        
        // Setup HUD panel
        setupHUD(ipc: ipc)
        
        // Automatically boot the Python core on launch!
        daemon.startDaemon()
        
        // Register global hotkey
        GlobalHotkeyManager.shared.register { [weak self] in
            self?.ipc.sendCommand("toggle_listening")
        }
    }
    
    func setupHUD(ipc: IPCBridge) {
        guard hudPanel == nil else { return }
        
        let panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 280, height: 360),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.level = .statusBar
        panel.backgroundColor = .clear
        panel.isOpaque = false
        panel.hasShadow = false
        panel.ignoresMouseEvents = true // Click-through by default when idle
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle]
        
        let hostingView = NSHostingView(rootView: FloatingHUDWindow(ipc: ipc))
        panel.contentView = hostingView
        
        // Position at top-center of the screen
        if let screen = NSScreen.main {
            let screenFrame = screen.visibleFrame
            let x = screenFrame.midX - 140
            let y = screenFrame.maxY - 360 - 8
            panel.setFrame(NSRect(x: x, y: y, width: 280, height: 360), display: true)
        }
        
        panel.orderFrontRegardless()
        self.hudPanel = panel
    }
    
    func applicationWillTerminate(_ notification: Notification) {
        print("Application terminating — cleanly stopping F.R.I.D.A.Y. daemon...")
        daemon.stopDaemon()
    }
}

@main
struct FridayUIApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    
    var body: some Scene {
        // Status menu bar item and dropdown
        MenuBarExtra {
            MenuDropdownView(ipc: appDelegate.ipc, daemon: appDelegate.daemon)
        } label: {
            HStack {
                Image("friday-icon-menubar")
                if appDelegate.ipc.state == "listening" {
                    Text("•")
                }
            }
        }
        .menuBarExtraStyle(.window) // Configures the menu bar popover as an interactive SwiftUI view
    }
}



