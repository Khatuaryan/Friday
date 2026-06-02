import Cocoa
import ApplicationServices

class SystemContextReader {
    
    /// Inspects the frontmost application window and retrieves selected text or tab context
    static func getActiveWindowContext() -> [String: String] {
        var context: [String: String] = [:]
        
        // 1. Identify the active application in focus
        guard let activeApp = NSWorkspace.shared.frontmostApplication else {
            return context
        }
        
        context["app_name"] = activeApp.localizedName ?? "System Window"
        context["bundle_id"] = activeApp.bundleIdentifier ?? ""
        
        // 2. Query accessibility tree elements
        let appElement = AXUIElementCreateApplication(activeApp.processIdentifier)
        var focusedWindow: AnyObject?
        
        if AXUIElementCopyAttributeValue(appElement, kAXFocusedWindowAttribute as CFString, &focusedWindow) == .success,
           let windowRef = focusedWindow as! AXUIElement? {
            
            // Retrieve active window title
            var titleVal: AnyObject?
            if AXUIElementCopyAttributeValue(windowRef, kAXTitleAttribute as CFString, &titleVal) == .success,
               let windowTitle = titleVal as? String {
                context["window_title"] = windowTitle
            }
            
            // Retrieve highlighted/selected text context (e.g. text selected inside Safari or Notes)
            var selectedTextVal: AnyObject?
            if AXUIElementCopyAttributeValue(windowRef, kAXSelectedTextAttribute as CFString, &selectedTextVal) == .success,
               let selectedText = selectedTextVal as? String {
                context["selected_text"] = selectedText
            }
        }
        
        return context
    }
}
