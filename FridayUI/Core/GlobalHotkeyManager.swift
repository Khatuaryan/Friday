import Cocoa
import Carbon

class GlobalHotkeyManager {
    static let shared = GlobalHotkeyManager()
    private var hotKeyRef: EventHotKeyRef?
    private var onTrigger: (() -> Void)?
    
    /// Registers system-wide trigger (Option + Space)
    func register(handler: @escaping () -> Void) {
        self.onTrigger = handler
        
        var hotKeyID = EventHotKeyID()
        hotKeyID.signature = OSType(101) // Unique registration signature
        hotKeyID.id = UInt32(1)
        
        var eventType = EventTypeSpec()
        eventType.eventClass = OSType(kEventClassKeyboard)
        eventType.eventType = UInt32(kEventHotKeyPressed)
        
        let pointer = UnsafeMutableRawPointer(Unmanaged.passUnretained(self).toOpaque())
        
        // Set up OS event listener
        InstallApplicationEventHandler({ (nextHandler, theEvent, userData) -> OSStatus in
            var hkID = EventHotKeyID()
            GetEventParameter(
                theEvent,
                EventParamName(kEventParamDirectObject),
                EventParamType(typeEventHotKeyID),
                nil,
                MemoryLayout<EventHotKeyID>.size,
                nil,
                &hkID
            )
            
            if hkID.id == UInt32(1) {
                DispatchQueue.main.async {
                    GlobalHotkeyManager.shared.onTrigger?()
                }
                return noErr
            }
            return CallNextEventHandler(nextHandler, theEvent)
        }, 1, &eventType, pointer, nil)
        
        // Key code 49 = Spacebar. optionKey = Option modifier key.
        RegisterEventHotKey(
            UInt32(49),
            UInt32(optionKey),
            hotKeyID,
            GetApplicationEventTarget(),
            0,
            &hotKeyRef
        )
        print("Global Hotkey Registered: [Option + Space]")
    }
}
