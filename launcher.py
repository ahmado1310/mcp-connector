#!/usr/bin/env python3
"""
MCP Connector Launcher
Starts all MCP servers (ADO, Docupedia) in parallel with live log output
"""

import subprocess
import sys
import time
import signal
import threading
from pathlib import Path
from typing import List

class ServerLauncher:
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        self.root_dir = Path(__file__).parent
        
    def stream_output(self, process: subprocess.Popen, name: str, stream_type: str):
        """Stream output from a process with prefix"""
        stream = process.stdout if stream_type == 'stdout' else process.stderr
        
        try:
            for line in iter(stream.readline, ''):
                if line:
                    print(f"[{name}] {line}", end='')
        except Exception as e:
            print(f"[{name}] Stream error: {e}")
        finally:
            stream.close()
    
    def start_server(self, name: str, script_path: str) -> subprocess.Popen:
        """Start a server process with live output streaming"""
        full_path = self.root_dir / script_path
        print(f"[{name}] Starting {script_path}...")
        
        process = subprocess.Popen(
            [sys.executable, str(full_path)],
            cwd=self.root_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Start threads to stream stdout and stderr
        stdout_thread = threading.Thread(
            target=self.stream_output,
            args=(process, name, 'stdout'),
            daemon=True
        )
        stderr_thread = threading.Thread(
            target=self.stream_output,
            args=(process, name, 'stderr'),
            daemon=True
        )
        
        stdout_thread.start()
        stderr_thread.start()
        
        self.processes.append(process)
        print(f"[{name}] Started with PID {process.pid}")
        return process
    
    def stop_all(self):
        """Stop all running processes"""
        print("\nStopping all servers...")
        for process in self.processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception as e:
                print(f"Error stopping process {process.pid}: {e}")
        print("All servers stopped")
    
    def run(self):
        """Start all servers and wait"""
        print("=" * 60)
        print("MCP Connector Launcher - Live Logs")
        print("=" * 60)
        print()
        
        try:
            # Start MCP servers
            self.start_server("ADO", "mcp-ado/mcp_server.py")
            time.sleep(2)
            
            self.start_server("Docupedia", "mcp-docupedia/mcp_server.py")
            time.sleep(2)
            
            print()
            print("=" * 60)
            print("All MCP servers started - Streaming logs below")
            print("=" * 60)
            print()
            print("Services:")
            print("  - MCP ADO Server:       http://localhost:8003/mcp")
            print("  - MCP Docupedia Server: http://localhost:8004/mcp")
            print()
            print("To start the Gateway UI, run in a separate terminal:")
            print("  uv run python mcp-gateway/ui.py")
            print()
            print("Press Ctrl+C to stop all servers")
            print("-" * 60)
            print()
            
            # Wait for processes
            while True:
                time.sleep(1)
                # Check if any process has died
                for i, process in enumerate(self.processes):
                    if process.poll() is not None:
                        print(f"\nProcess {i+1} (PID {process.pid}) has terminated!")
                        raise RuntimeError(f"Process {i+1} terminated unexpectedly")
        
        except KeyboardInterrupt:
            print("\n\nReceived interrupt signal")
        except Exception as e:
            print(f"\nError: {e}")
        finally:
            self.stop_all()

def main():
    launcher = ServerLauncher()
    
    # Handle signals
    def signal_handler(sig, frame):
        launcher.stop_all()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    launcher.run()

if __name__ == "__main__":
    main()
