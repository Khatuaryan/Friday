import Cocoa

class GlobalHotkeyManager {
    static let shared = GlobalHotkeyManager()
    private var onTrigger: (() -> Void)?
    
    /// Registers system-wide trigger (Option + Space) using non-blocking Cocoa event taps
    func register(handler: @escaping () -> Void) {
        self.onTrigger = handler
        
        // 1. Listen for Option + Space in the background
        NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { [weak self] event in
            if event.modifierFlags.contains(.option) && event.keyCode == 49 {
                DispatchQueue.main.async {
                    self?.onTrigger?()
                }
            }
        }
        
        // 2. Listen for Option + Space when the app is active in the foreground
        NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
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
}
