import Cocoa

class GlobalHotkeyManager {
    static let shared = GlobalHotkeyManager()
    private var onTrigger: (() -> Void)?
    private var globalMonitor: Any?
    private var localMonitor: Any?
    private var isRegistered = false
    
    /// Registers system-wide trigger (Option + Space) using non-blocking Cocoa event taps
    func register(handler: @escaping () -> Void) {
        guard !isRegistered else { return }
        isRegistered = true
        self.onTrigger = handler
        
        // 1. Listen for Option + Space in the background
        globalMonitor = NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { [weak self] event in
            if event.modifierFlags.contains(.option) && event.keyCode == 49 {
                DispatchQueue.main.async {
                    self?.onTrigger?()
                }
            }
        }
        
        // 2. Listen for Option + Space when the app is active in the foreground
        localMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            if event.modifierFlags.contains(.option) && event.keyCode == 49 {
                DispatchQueue.main.async {
                    self?.onTrigger?()
                }
                return nil // Swallow event to prevent spacebar entry in active text fields
            }
            return event
        }
        
        print("Global Hotkey Registered via NSEvent: [Option + Space]")
    }
    
    func unregister() {
        if let m = globalMonitor { NSEvent.removeMonitor(m) }
        if let m = localMonitor { NSEvent.removeMonitor(m) }
        globalMonitor = nil
        localMonitor = nil
        isRegistered = false
        print("Global Hotkey Unregistered")
    }
}
