#!/usr/bin/env python3
"""
Integrated Terminal UI Dashboard for MCP Gateway using Rich
This version loads the gateway as a module instead of using network connections
Features:
- Direct access to gateway state
- Live updating server status
- Request monitoring
- Health indicators
- Keyboard shortcuts
"""

import asyncio
import threading
import time
import logging
import contextlib
from datetime import datetime
from typing import Dict, List, Any, Optional
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.console import Console, Group
from rich.align import Align
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich import box
import json
from pathlib import Path
import sys
import uvicorn
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

# Suppress ALL logging output in UI mode
import os
import io

# Set root logger to ERROR
logging.basicConfig(level=logging.ERROR, format='')
logging.getLogger().setLevel(logging.ERROR)

# Suppress specific loggers
for logger_name in ['uvicorn', 'uvicorn.access', 'uvicorn.error', 'fastmcp', 
                    'gateway_server', '__main__', 'mcp_server', 'rich']:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

# Import gateway components
from gateway_server import (
    gateway, 
    state, 
    load_child_servers,
    LoggingMiddleware,
    utc_now,
    logger
)

# Override gateway logger completely
logger.setLevel(logging.CRITICAL)
logger.handlers = []  # Remove all handlers

# Also suppress demo server logger if it gets imported
try:
    import mcp_server
    if hasattr(mcp_server, 'logger'):
        mcp_server.logger.setLevel(logging.CRITICAL)
        mcp_server.logger.handlers = []
except:
    pass

console = Console()

class IntegratedGatewayDashboard:
    def __init__(self, port: int = 8001):
        self.port = port
        self.layout = self.create_layout()
        self.running = True
        self.last_update = None
        self.gateway_thread = None
        self.server = None
        
    def create_layout(self) -> Layout:
        """Create the dashboard layout"""
        layout = Layout()
        
        # Main layout structure - all horizontal cards
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="servers", ratio=2),
            Layout(name="info", ratio=1),
            Layout(name="footer", size=1)
        )
        
        return layout
    
    def make_header(self) -> Panel:
        """Create header panel"""
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="center", ratio=1)
        grid.add_column(justify="right", ratio=1)
        
        # Title
        title = Text("MCP Gateway Dashboard", style="bold blue")
        
        # Connection Status
        active_clients = len(state.active_connections)
        if active_clients > 0:
            status = Text(f"Port: {self.port} | [green]● {active_clients} client(s)[/green]", style="green")
        else:
            status = Text(f"Port: {self.port} | [yellow]○ Awaiting connection[/yellow]", style="yellow")
        
        # Time
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        time_text = Text(current_time, style="cyan")
        
        grid.add_row(title, status, time_text)
        
        return Panel(grid, box=box.ROUNDED)
    
    def make_servers_table(self) -> Table:
        """Create servers status table"""
        table = Table(title="Child Servers", box=box.ROUNDED, expand=True)
        
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Type", style="magenta")
        table.add_column("Prefix", style="yellow")
        table.add_column("Connection", style="green")
        table.add_column("Status", style="green")
        table.add_column("Reqs.", justify="right")
        table.add_column("Errors", justify="right")
        table.add_column("Avg Latency", justify="right")
        
        # Get server data directly from state
        for name, info in state.child_servers.items():
            server_type = info.get("type", "unknown")
            prefix = info.get("prefix", "")
            
            # Get metrics
            metrics = state.metrics.get(name, {})
            status = metrics.get("status", "idle")
            requests = metrics.get("request_count", 0)
            errors = metrics.get("error_count", 0)
            
            # Calculate average latency
            avg_latency = "N/A"
            if requests > 0 and "total_latency" in metrics:
                avg = metrics["total_latency"] / requests
                avg_latency = f"{avg:.2f}ms"
            
            # Connection status for this server
            conn_status = metrics.get("connection_status", "unknown")
            if conn_status == "connected":
                connection_status = "[green]● Connected[/green]"
            elif conn_status == "failed":
                connection_status = "[red]✗ Failed[/red]"
            elif conn_status == "disconnected":
                connection_status = "[yellow]○ Disconnected[/yellow]"
            elif conn_status == "unhealthy":
                connection_status = "[yellow]⚠ Unhealthy[/yellow]"
            else:
                connection_status = "[gray]○ Not Checked[/gray]"
            
            # Status color
            if status == "healthy":
                status_style = "[green]Healthy[/green]"
            elif status == "error":
                status_style = "[red]Error[/red]"
            elif status == "unhealthy":
                status_style = "[yellow]Unhealthy[/yellow]"
            else:
                status_style = "[gray]Idle[/gray]"
            
            table.add_row(
                name,
                server_type,
                f"/{prefix}" if prefix else "/",
                connection_status,
                status_style,
                str(requests),
                str(errors) if errors > 0 else "[green]0[/green]",
                avg_latency
            )
        
        if not state.child_servers:
            table.add_row("[gray]No servers configured[/gray]", "", "", "", "", "", "")
        
        return table
    
    def make_info_panel(self) -> Panel:
        """Create horizontal info panel with gateway stats and activity"""
        # Create a table with multiple columns for horizontal layout
        grid = Table.grid(expand=True, padding=1)
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        
        # Calculate uptime
        uptime = (utc_now() - state.start_time).total_seconds()
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)
        
        # Gateway Stats
        stats_text = []
        stats_text.append("[bold cyan]Gateway Stats[/bold cyan]")
        stats_text.append(f"Uptime: {hours:02d}:{minutes:02d}:{seconds:02d}")
        stats_text.append(f"Requests: {state.request_count}")
        stats_text.append(f"Errors: {state.error_count}")
        error_rate = 0
        if state.request_count > 0:
            error_rate = (state.error_count / state.request_count) * 100
        stats_text.append(f"Error Rate: {error_rate:.1f}%")
        
        # Server Summary
        server_text = []
        server_text.append("[bold cyan]Server Summary[/bold cyan]")
        server_text.append(f"Total: {len(state.child_servers)}")
        connected = sum(1 for m in state.metrics.values() if m.get("connection_status") == "connected")
        server_text.append(f"Connected: {connected}")
        failed = sum(1 for m in state.metrics.values() if m.get("connection_status") in ["failed", "disconnected"])
        if failed > 0:
            server_text.append(f"[yellow]Failed: {failed}[/yellow]")
        else:
            server_text.append(f"Failed: 0")
        
        # MCP Clients
        client_text = []
        client_text.append("[bold cyan]MCP Clients[/bold cyan]")
        
        # Clean up old connections
        current_time = utc_now()
        for client_addr in list(state.active_connections.keys()):
            last_seen_str = state.active_connections[client_addr]["last_seen"]
            last_seen = datetime.fromisoformat(last_seen_str.replace('+00:00', ''))
            if hasattr(last_seen, 'tzinfo') and last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=current_time.tzinfo)
            
            time_diff = (current_time - last_seen).total_seconds()
            if time_diff > 30:
                del state.active_connections[client_addr]
        
        active_clients = len(state.active_connections)
        if active_clients > 0:
            client_text.append(f"[green]Active: {active_clients}[/green]")
            for addr, info in list(state.active_connections.items())[:2]:
                client_text.append(f"[dim]{addr.split(':')[0]}[/dim]")
        else:
            client_text.append("[yellow]None connected[/yellow]")
        
        # Recent Activity
        activity_text = []
        activity_text.append("[bold cyan]Recent Activity[/bold cyan]")
        
        # Show last few server checks
        recent_checks = []
        for name, metrics in state.metrics.items():
            if metrics.get("last_check"):
                recent_checks.append((metrics["last_check"], name, metrics.get("connection_status", "unknown")))
        
        recent_checks.sort(reverse=True)
        for check_time, name, status in recent_checks[:3]:
            if status == "connected":
                activity_text.append(f"[green]✓[/green] {name[:15]}")
            elif status == "failed":
                activity_text.append(f"[red]✗[/red] {name[:15]}")
            else:
                activity_text.append(f"[yellow]?[/yellow] {name[:15]}")
        
        if not recent_checks:
            activity_text.append("[gray]No activity[/gray]")
        
        # Add columns to grid
        grid.add_row(
            "\n".join(stats_text),
            "\n".join(server_text),
            "\n".join(client_text),
            "\n".join(activity_text)
        )
        
        return Panel(grid, title="Gateway Information", box=box.ROUNDED)
    
    def make_footer(self) -> Panel:
        """Create footer panel"""
        footer_text = "[bold]Commands:[/bold] [yellow]q[/yellow] Quit | [yellow]r[/yellow] Refresh | [yellow]h[/yellow] Health Check"
        return Panel(footer_text, box=box.ROUNDED, style="dim")
    
    async def update_display(self) -> None:
        """Update the display"""
        self.last_update = datetime.now()
        
        # Check server connections periodically (every 5 seconds)
        if not hasattr(self, 'last_connection_check'):
            self.last_connection_check = datetime.now()
        
        if (datetime.now() - self.last_connection_check).total_seconds() > 5:
            # Run connection check in background thread to avoid blocking
            threading.Thread(target=state.check_server_connections, daemon=True).start()
            self.last_connection_check = datetime.now()
        
        # Update layout components
        self.layout["header"].update(self.make_header())
        self.layout["servers"].update(self.make_servers_table())
        self.layout["info"].update(self.make_info_panel())
        self.layout["footer"].update(self.make_footer())
    
    def start_gateway_server(self):
        """Start the gateway server in a background thread"""
        
        # Create a custom LoggingMiddleware that doesn't log
        class SilentLoggingMiddleware:
            def __init__(self, app):
                self.app = app
            
            async def __call__(self, scope, receive, send):
                if scope["type"] == "http":
                    path = scope["path"]
                    method = scope["method"]
                    
                    # Still track connections for the UI
                    if path == "/mcp" and method == "POST":
                        client = scope.get("client", ("unknown", 0))
                        client_addr = f"{client[0]}:{client[1]}"
                        state.last_activity = utc_now()
                        state.active_connections[client_addr] = {
                            "connected_at": utc_now().isoformat(),
                            "last_seen": utc_now().isoformat(),
                            "requests": state.active_connections.get(client_addr, {}).get("requests", 0) + 1
                        }
                
                await self.app(scope, receive, send)
        
        async def run_server():
            # Set UI mode environment variable to suppress module logging
            os.environ['MCP_UI_MODE'] = '1'
            
            # Suppress output during initialization
            import contextlib
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                # Initialize gateway
                await load_child_servers()
            
            # After loading, suppress logging in all loaded modules
            import sys
            for module_name, module in sys.modules.items():
                if 'mcp' in module_name or 'demo' in module_name:
                    # Check for logger attribute
                    if hasattr(module, 'logger'):
                        module.logger.setLevel(logging.CRITICAL)
                        module.logger.handlers = []
                    # Also check for logging configuration
                    if hasattr(module, 'logging'):
                        try:
                            module.logging.getLogger().setLevel(logging.CRITICAL)
                        except:
                            pass
            
            # Specifically handle the demo server if it's loaded
            if 'mcp_server' in sys.modules:
                demo_module = sys.modules['mcp_server']
                if hasattr(demo_module, 'logger'):
                    demo_module.logger.setLevel(logging.CRITICAL)
                    demo_module.logger.handlers = []
                # Replace its LoggingMiddleware with our silent version
                if hasattr(demo_module, 'LoggingMiddleware'):
                    demo_module.LoggingMiddleware = SilentLoggingMiddleware
            
            # Check initial connection status
            state.check_server_connections()
            
            # Define middleware
            custom_middleware = [
                Middleware(
                    CORSMiddleware,
                    allow_origins=["*"],
                    allow_credentials=True,
                    allow_methods=["GET", "POST", "OPTIONS"],
                    allow_headers=["*"],
                    expose_headers=["mcp-session-id", "Mcp-Session-Id", "*"]
                ),
                Middleware(SilentLoggingMiddleware),  # Use silent version
            ]
            
            # Create ASGI app
            http_app = gateway.http_app(
                path="/mcp",
                middleware=custom_middleware
            )
            
            # Run server
            config = uvicorn.Config(
                http_app,
                host="127.0.0.1",
                port=self.port,
                log_level="error",  # Only show errors
                access_log=False    # Disable access logging
            )
            self.server = uvicorn.Server(config)
            await self.server.serve()
        
        def run_in_thread():
            asyncio.run(run_server())
        
        self.gateway_thread = threading.Thread(target=run_in_thread, daemon=True)
        self.gateway_thread.start()
        
        # Give server time to start
        time.sleep(1)
    
    async def run(self) -> None:
        """Run the dashboard"""
        # Start the gateway server
        self.start_gateway_server()
        
        # Override print to prevent any output
        import builtins
        original_print = builtins.print
        builtins.print = lambda *args, **kwargs: None
        
        try:
            # Run the dashboard
            with Live(self.layout, refresh_per_second=1, screen=True) as live:
                while self.running:
                    try:
                        await self.update_display()
                        
                        # Check for keyboard input (non-blocking)
                        await asyncio.sleep(1)
                        
                    except KeyboardInterrupt:
                        self.running = False
                    except Exception as e:
                        # Don't print errors to console during live display
                        await asyncio.sleep(1)
        finally:
            # Restore print function
            builtins.print = original_print
            
            # Cleanup
            if self.server:
                self.server.should_exit = True

def main():
    """Main entry point"""
    import sys
    
    # Get port from command line or use default
    port = 8001
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            console.print(f"[red]Invalid port: {sys.argv[1]}[/red]")
            sys.exit(1)
    
    # Create and run dashboard
    dashboard = IntegratedGatewayDashboard(port=port)
    
    console.print("[bold blue]Starting MCP Gateway Dashboard (Integrated Mode)[/bold blue]")
    console.print(f"[green]Gateway will run on port {port}[/green]")
    console.print("[yellow]Press Ctrl+C to exit[/yellow]")
    
    try:
        asyncio.run(dashboard.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()