import Foundation
import Combine

class IPCBridge: ObservableObject {
    @Published var state: String = "offline"
    @Published var memoryPressure: String = "unknown"
    @Published var rssMB: Double = 0.0
    
    private var timer: Timer?
    private let statusURL: URL
    private let commandDirURL: URL
    
    init() {
        let homeDir = FileManager.default.homeDirectoryForCurrentUser
        self.statusURL = homeDir.appendingPathComponent(".cache/friday/status.json")
        self.commandDirURL = homeDir.appendingPathComponent(".cache/friday/commands")
        
        // Ensure commands folder exists
        try? FileManager.default.createDirectory(at: commandDirURL, withIntermediateDirectories: true)
        
        // Poll status.json every 0.1s for ultra-fast state changes (listening, speaking, etc.)
        self.timer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            self?.pollStatus()
        }
    }
    
    // Python -> Swift: Read status.json
    private func pollStatus() {
        guard FileManager.default.fileExists(atPath: statusURL.path) else {
            // Inside IPCBridge.swift's pollStatus():
            DispatchQueue.main.async {
                let oldState = self.state
                self.state = json["state"] as? String ?? "ready"
                self.rssMB = json["rss_mb"] as? Double ?? 0.0
                self.memoryPressure = json["pressure"] as? String ?? "unknown"
                
                // Trigger premium trackpad click only on a clean activation transition
                if self.state == "listening" && oldState != "listening" {
                    NSHapticFeedbackManager.defaultPerformer.perform(.generic, performanceTime: .default)
                }
            }

            return
        }
        
        do {
            let data = try Data(contentsOf: statusURL)
            if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] {
                DispatchQueue.main.async {
                    self.state = json["state"] as? String ?? "ready"
                    self.rssMB = json["rss_mb"] as? Double ?? 0.0
                    self.memoryPressure = json["pressure"] as? String ?? "unknown"
                }
            }
        } catch {
            print("Failed to read IPC status: \(error)")
        }
    }
    
    // Swift -> Python: Write command files
    func sendCommand(_ command: String) {
        let fileURL = commandDirURL.appendingPathComponent("\(command).cmd")
        do {
            try "".write(to: fileURL, atomically: true, encoding: .utf8)
            print("Sent IPC Command: \(command)")
        } catch {
            print("Failed to send IPC command: \(error)")
        }
    }
}
