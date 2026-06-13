import Foundation
import Combine

class DaemonManager: ObservableObject {
    @Published var isRunning = false
    private var process: Process?
    private let pidFileURL: URL
    private let pythonPath: URL
    private let workingDirectory: URL
    
    init() {
        let homeDir = FileManager.default.homeDirectoryForCurrentUser
        self.pidFileURL = homeDir.appendingPathComponent(".cache/friday/friday.pid")
        
        // Define paths exactly matching your workspace
        self.workingDirectory = homeDir.appendingPathComponent("PycharmProjects/Friday")
        self.pythonPath = workingDirectory.appendingPathComponent(".venv/bin/python")
        
        checkStatus()
    }
    
    /// Queries system state to check if the Python PID is active
    func checkStatus() {
        if FileManager.default.fileExists(atPath: pidFileURL.path),
           let pidString = try? String(contentsOf: pidFileURL, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines),
           let pid = Int32(pidString) {
            // Check if process with PID is alive using signal 0
            let result = kill(pid, 0)
            DispatchQueue.main.async {
                self.isRunning = (result == 0)
            }
        } else {
            DispatchQueue.main.async {
                self.isRunning = false
            }
        }
    }
    
    /// Spawns the background Python daemon and redirects log handles
    func startDaemon() {
        // Clean stale PID if process is dead
        if FileManager.default.fileExists(atPath: pidFileURL.path),
           let pidString = try? String(contentsOf: pidFileURL, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines),
           let pid = Int32(pidString) {
            if kill(pid, 0) != 0 {
                // Process is dead, remove stale PID
                try? FileManager.default.removeItem(at: pidFileURL)
                print("Removed stale PID file for dead process \(pid)")
                self.isRunning = false
            } else {
                print("Daemon already running with PID \(pid)")
                self.isRunning = true
                return
            }
        } else {
            self.isRunning = false
        }
        
        guard !isRunning else { return }
        
        guard FileManager.default.fileExists(atPath: pythonPath.path) else {
            print("Error: Python virtual environment not found at \(pythonPath.path)")
            return
        }
        
        let proc = Process()
        proc.executableURL = pythonPath
        proc.arguments = ["-m", "src.core", "--no-face"]
        proc.currentDirectoryURL = workingDirectory
        
        // Provide standard macOS environment paths
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        env["FRIDAY_NO_OVERLAY"] = "1" // Disable legacy Tkinter overlay for native Swift UI
        proc.environment = env
        
        // Redirect stdout and stderr streams to log files
        let logDir = workingDirectory.appendingPathComponent("logs")
        try? FileManager.default.createDirectory(at: logDir, withIntermediateDirectories: true)
        
        let stdoutLog = logDir.appendingPathComponent("daemon_stdout.log")
        let stderrLog = logDir.appendingPathComponent("daemon_stderr.log")
        
        FileManager.default.createFile(atPath: stdoutLog.path, contents: nil)
        FileManager.default.createFile(atPath: stderrLog.path, contents: nil)
        
        if let stdoutHandle = try? FileHandle(forWritingTo: stdoutLog),
           let stderrHandle = try? FileHandle(forWritingTo: stderrLog) {
            proc.standardOutput = stdoutHandle
            proc.standardError = stderrHandle
        }
        
        do {
            try proc.run()
            self.process = proc
            DispatchQueue.main.async {
                self.isRunning = true
            }
            print("F.R.I.D.A.Y. Python Daemon started (PID: \(proc.processIdentifier))")
        } catch {
            print("Failed to execute Python core process: \(error)")
        }
    }
    
    /// Kills the background daemon using graceful SIGTERM
    func stopDaemon() {
        if FileManager.default.fileExists(atPath: pidFileURL.path),
           let pidString = try? String(contentsOf: pidFileURL, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines),
           let pid = Int32(pidString) {
            kill(pid, 15) // 15 = SIGTERM (Clean shutdown)
            print("Sent SIGTERM to Daemon PID \(pid)")
        }
        
        if let proc = process, proc.isRunning {
            proc.terminate()
        }
        
        DispatchQueue.main.async {
            self.isRunning = false
        }
        process = nil
    }
}
