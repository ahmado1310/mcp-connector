#!/usr/bin/env python3
"""
MCP Gateway Server using FastMCP v2
Features:
- Dynamic mounting/proxying of child servers
- CORS enabled for browser access  
- Request/response logging
- Health check endpoints
- Configurable via JSON
"""

from fastmcp import FastMCP
from fastmcp.server.proxy import ProxyClient
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import json
import logging
import asyncio
import httpx
import time
import sys
import importlib
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pathlib import Path
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize the MCP gateway
gateway = FastMCP("MCP Gateway Server")

# Helper function for UTC datetime
def utc_now():
    """Get current UTC datetime in a compatible way"""
    try:
        return datetime.now(timezone.utc)
    except AttributeError:
        # Fallback for older Python versions
        return datetime.utcnow()

# Store child server info and metrics
class GatewayState:
    def __init__(self):
        self.child_servers: Dict[str, Dict] = {}
        self.metrics: Dict[str, Dict] = {}
        self.start_time = utc_now()
        self.request_count = 0
        self.error_count = 0
        self.active_connections: Dict[str, Dict] = {}  # Track active MCP connections
        self.last_activity = utc_now()
        
    def update_metrics(self, server_name: str, latency: float, status: str):
        if server_name not in self.metrics:
            self.metrics[server_name] = {
                "request_count": 0,
                "error_count": 0,
                "total_latency": 0,
                "last_check": None,
                "status": "unknown",
                "connection_status": "disconnected"
            }
        
        self.metrics[server_name]["request_count"] += 1
        self.metrics[server_name]["total_latency"] += latency
        self.metrics[server_name]["last_check"] = utc_now().isoformat()
        self.metrics[server_name]["status"] = status
        
        # Update connection status based on result
        if status == "healthy":
            self.metrics[server_name]["connection_status"] = "connected"
        elif status == "error":
            self.metrics[server_name]["connection_status"] = "failed"
            self.metrics[server_name]["error_count"] += 1
            self.error_count += 1
        else:
            self.metrics[server_name]["connection_status"] = "unhealthy"
        
        self.request_count += 1
    
    def check_server_connections(self):
        """Check connection status for all servers"""
        import asyncio
        import httpx
        
        async def check_proxy(name, info):
            """Check if a proxy server is reachable"""
            if info["type"] != "proxy":
                return
            
            try:
                async with httpx.AsyncClient() as client:
                    url = info.get("url", "").replace("/mcp", "")
                    health_endpoint = info.get("health_endpoint", "/health")
                    if not health_endpoint.startswith("http"):
                        health_url = url + health_endpoint
                    else:
                        health_url = health_endpoint
                    
                    response = await client.get(health_url, timeout=2.0)
                    if response.status_code == 200:
                        if name not in self.metrics:
                            self.metrics[name] = {}
                        self.metrics[name]["connection_status"] = "connected"
                        self.metrics[name]["last_check"] = utc_now().isoformat()
                    else:
                        if name not in self.metrics:
                            self.metrics[name] = {}
                        self.metrics[name]["connection_status"] = "unhealthy"
            except:
                if name not in self.metrics:
                    self.metrics[name] = {}
                self.metrics[name]["connection_status"] = "disconnected"
        
        # Check module servers (always connected if loaded)
        for name, info in self.child_servers.items():
            if info["type"] == "module":
                if name not in self.metrics:
                    self.metrics[name] = {
                        "request_count": 0,
                        "error_count": 0,
                        "total_latency": 0,
                        "last_check": utc_now().isoformat(),
                        "status": "healthy"
                    }
                self.metrics[name]["connection_status"] = "connected"
        
        # Run proxy checks asynchronously
        async def run_checks():
            tasks = [check_proxy(name, info) for name, info in self.child_servers.items() if info["type"] == "proxy"]
            if tasks:
                await asyncio.gather(*tasks)
        
        try:
            # Try to get the current event loop
            loop = asyncio.get_running_loop()
            # Schedule the coroutine on the existing loop
            asyncio.create_task(run_checks())
        except RuntimeError:
            # No loop running, create a new one
            asyncio.run(run_checks())

state = GatewayState()

# ============= Health Check Routes =============

@gateway.custom_route("/", methods=["GET"])
def root(request: Request) -> PlainTextResponse:
    """Root endpoint"""
    return PlainTextResponse("MCP Gateway Server is running. Use /health for status.")

@gateway.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Gateway health check endpoint"""
    uptime = (utc_now() - state.start_time).total_seconds()
    
    return JSONResponse({
        "status": "healthy",
        "gateway": "MCP Gateway Server",
        "uptime_seconds": uptime,
        "total_requests": state.request_count,
        "total_errors": state.error_count,
        "child_servers": len(state.child_servers),
        "timestamp": utc_now().isoformat()
    })

@gateway.custom_route("/health/{server_name}", methods=["GET"])
async def server_health_check(request: Request) -> JSONResponse:
    """Individual server health check"""
    server_name = request.path_params["server_name"]
    
    if server_name not in state.child_servers:
        return JSONResponse({"error": f"Server '{server_name}' not found"}, status_code=404)
    
    server_info = state.child_servers[server_name]
    start_time = time.time()
    
    # Check health based on server type
    if server_info["type"] == "proxy":
        try:
            async with httpx.AsyncClient() as client:
                health_url = server_info.get("health_endpoint", "/health")
                if not health_url.startswith("http"):
                    health_url = server_info["url"].replace("/mcp", "") + health_url
                
                response = await client.get(health_url, timeout=5.0)
                latency = (time.time() - start_time) * 1000
                
                status = "healthy" if response.status_code == 200 else "unhealthy"
                state.update_metrics(server_name, latency, status)
                
                return JSONResponse({
                    "server": server_name,
                    "type": "proxy",
                    "status": status,
                    "latency_ms": round(latency, 2),
                    "response_code": response.status_code,
                    "timestamp": utc_now().isoformat()
                })
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            state.update_metrics(server_name, latency, "error")
            
            return JSONResponse({
                "server": server_name,
                "type": "proxy",
                "status": "error",
                "error": str(e),
                "latency_ms": round(latency, 2),
                "timestamp": utc_now().isoformat()
            }, status_code=503)
    else:
        # For mounted servers, just return OK
        latency = (time.time() - start_time) * 1000
        state.update_metrics(server_name, latency, "healthy")
        
        return JSONResponse({
            "server": server_name,
            "type": "mount",
            "status": "healthy",
            "latency_ms": round(latency, 2),
            "timestamp": utc_now().isoformat()
        })

@gateway.custom_route("/status", methods=["GET"])
async def status(request: Request) -> JSONResponse:
    """Get status of all servers"""
    servers_status = []
    
    for name, info in state.child_servers.items():
        server_status = {
            "name": name,
            "type": info["type"],
            "prefix": info.get("prefix", ""),
            "url": info.get("url", ""),
            "metrics": state.metrics.get(name, {})
        }
        
        # Calculate average latency
        if name in state.metrics and state.metrics[name]["request_count"] > 0:
            avg_latency = state.metrics[name]["total_latency"] / state.metrics[name]["request_count"]
            server_status["metrics"]["average_latency_ms"] = round(avg_latency, 2)
        
        servers_status.append(server_status)
    
    return JSONResponse({
        "gateway": {
            "status": "running",
            "uptime_seconds": (utc_now() - state.start_time).total_seconds(),
            "total_requests": state.request_count,
            "total_errors": state.error_count
        },
        "servers": servers_status,
        "timestamp": utc_now().isoformat()
    })

@gateway.custom_route("/metrics", methods=["GET"])
async def metrics(request: Request) -> JSONResponse:
    """Get detailed metrics"""
    return JSONResponse({
        "gateway_metrics": {
            "uptime_seconds": (utc_now() - state.start_time).total_seconds(),
            "total_requests": state.request_count,
            "total_errors": state.error_count,
            "error_rate": state.error_count / max(state.request_count, 1)
        },
        "server_metrics": state.metrics,
        "timestamp": utc_now().isoformat()
    })

# ============= Configuration Loading =============

async def load_child_servers(config_path: str = ""):
    """Load and mount/proxy child servers from configuration"""

    if not config_path:
        config_path = os.path.join(os.path.dirname(__file__), "gateway_config.json")

    config_file = Path(config_path)
    
    if not config_file.exists():
        logger.warning(f"Configuration file {config_path} not found, using defaults")
        return
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        logger.info(f"Loading configuration from {config_path}")
        
        # Process child servers
        for server_config in config.get("child_servers", []):
            name = server_config["name"]
            server_type = server_config["type"]
            prefix = server_config.get("prefix", "")
            
            logger.info(f"Registering {server_type} server '{name}' with prefix '{prefix}'")
            
            if server_type == "proxy":
                # For proxy servers, create a client and mount it
                url = server_config["url"]
                
                # Handle authentication if configured
                headers = {}
                if "auth" in server_config:
                    auth = server_config["auth"]
                    if auth["type"] == "bearer":
                        token = os.environ.get(auth["token"], auth["token"])
                        headers["Authorization"] = f"Bearer {token}"
                
                try:
                    # Create FastMCP proxy for the remote server using ProxyClient
                    proxy_client = ProxyClient(url)
                    proxy_server = FastMCP.as_proxy(proxy_client, name=name)
                    
                    # Mount the proxy server
                    gateway.mount(proxy_server, prefix=prefix)
                    
                    logger.info(f"Successfully mounted proxy server '{name}' at prefix '{prefix}'")
                    
                except Exception as e:
                    logger.error(f"Failed to mount proxy server '{name}': {e}")
                    continue
                    
            elif server_type == "module":
                # For local module servers, import and mount the module
                module_path = server_config.get("module_path", "")
                module_name = server_config.get("module_name", "mcp_server")
                init_function = server_config.get("init_function", "initialize")
                module_envvars = server_config.get("module_envvars", {})
                
                try:
                    import sys
                    import importlib.util

                    for envvar_name, envvar_value in module_envvars.items():
                        if envvar_name:
                            os.environ[envvar_name] = envvar_value
                            logger.info(f"Set environment variable for module {module_name}: {envvar_name} = {envvar_value}")
                    
                    # Handle module path resolution
                    if module_path:
                        # Convert to absolute path
                        if Path(module_path).is_absolute():
                            # Already absolute
                            module_abs_path = Path(module_path)
                        else:
                            # Relative path - resolve relative to config file location
                            config_dir = Path(config_path).parent if config_path else Path.cwd()
                            module_abs_path = (config_dir / module_path).resolve()
                        
                        logger.info(f"Resolved module path to: {module_abs_path}")
                        
                        if not module_abs_path.exists():
                            logger.error(f"Module path does not exist: {module_abs_path}")
                            continue
                        
                        # Add the parent directory to sys.path for package imports
                        parent_path = str(module_abs_path.parent)
                        if parent_path not in sys.path:
                            sys.path.insert(0, parent_path)
                            logger.info(f"Added {parent_path} to sys.path")
                        
                        # Try different import strategies
                        module = None
                        
                        # Strategy 1: If module_path points to a .py file, import it directly
                        if module_abs_path.is_file() and module_abs_path.suffix == '.py':
                            spec = importlib.util.spec_from_file_location(module_name, module_abs_path)
                            if spec and spec.loader:
                                module = importlib.util.module_from_spec(spec)
                                sys.modules[module_name] = module  # Add to sys.modules cache
                                spec.loader.exec_module(module)
                                logger.info(f"Imported module from file: {module_abs_path}")
                        
                        # Strategy 2: If module_path points to a directory, try package import
                        elif module_abs_path.is_dir():
                            # Check if it's a package (has __init__.py)
                            init_file = module_abs_path / "__init__.py"
                            if init_file.exists():
                                package_name = module_abs_path.name.replace("-", "_")
                                try:
                                    module = importlib.import_module(package_name)
                                    logger.info(f"Imported package: {package_name}")
                                except ImportError as e:
                                    logger.warning(f"Failed to import package {package_name}: {e}")
                            
                            # Try importing the specific module file from the directory
                            if not module:
                                module_file = module_abs_path / f"{module_name}.py"
                                if module_file.exists():
                                    spec = importlib.util.spec_from_file_location(module_name, module_file)
                                    if spec and spec.loader:
                                        module = importlib.util.module_from_spec(spec)
                                        sys.modules[module_name] = module
                                        spec.loader.exec_module(module)
                                        logger.info(f"Imported module file: {module_file}")
                        
                        if not module:
                            logger.error(f"Could not import module from path: {module_abs_path}")
                            continue
                    
                    else:
                        # No module_path specified, try to import by name
                        try:
                            module = importlib.import_module(module_name)
                            logger.info(f"Imported module by name: {module_name}")
                        except ImportError as e:
                            logger.error(f"Failed to import module '{module_name}': {e}")
                            continue
                    
                    # Initialize the module if function provided
                    if hasattr(module, init_function):
                        init_func = getattr(module, init_function)
                        local_server = init_func()
                        logger.info(f"Initialized module using {init_function}()")
                    elif hasattr(module, 'mcp'):
                        local_server = module.mcp
                        logger.info(f"Using module.mcp directly")
                    elif hasattr(module, 'server'):
                        local_server = module.server
                        logger.info(f"Using module.server directly")
                    else:
                        logger.error(f"Module '{module_name}' has no 'mcp', 'server' attribute or '{init_function}' function")
                        continue
                    
                    # Mount the local server
                    gateway.mount(local_server, prefix=prefix)
                    
                    logger.info(f"Successfully mounted module server '{name}' at prefix '{prefix}'")
                    
                except Exception as e:
                    logger.error(f"Failed to mount module server '{name}': {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    continue
            
            # Store server info for health checks
            state.child_servers[name] = server_config
            
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")

# ============= Demo Tools (for testing) =============

@gateway.tool
def gateway_info() -> Dict[str, Any]:
    """Get gateway information"""
    return {
        "name": "MCP Gateway Server",
        "version": "1.0.0",
        "child_servers": len(state.child_servers),
        "uptime_seconds": (utc_now() - state.start_time).total_seconds(),
        "timestamp": utc_now().isoformat()
    }

@gateway.tool
def list_servers() -> List[Dict[str, Any]]:
    """List all registered child servers"""
    servers = []
    for name, info in state.child_servers.items():
        servers.append({
            "name": name,
            "type": info["type"],
            "prefix": info.get("prefix", ""),
            "url": info.get("url", "N/A")
        })
    return servers

# ============= Logging Middleware =============

class LoggingMiddleware:
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            start_time = time.time()
            path = scope["path"]
            method = scope["method"]
            
            # Extract client info
            client = scope.get("client", ("unknown", 0))
            client_addr = f"{client[0]}:{client[1]}"
            
            # Log request
            logger.info(f"[{method}] {path} from {client_addr}")
            
            # Track MCP connections
            if path == "/mcp" and method == "POST":
                state.last_activity = utc_now()
                # Track connection
                state.active_connections[client_addr] = {
                    "connected_at": utc_now().isoformat(),
                    "last_seen": utc_now().isoformat(),
                    "requests": state.active_connections.get(client_addr, {}).get("requests", 0) + 1
                }
            
            # Track response status
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    status = message.get("status", 0)
                    duration = (time.time() - start_time) * 1000
                    logger.info(f"[{method}] {path} -> {status} ({duration:.2f}ms)")
                    
                    # Update connection last seen
                    if client_addr in state.active_connections:
                        state.active_connections[client_addr]["last_seen"] = utc_now().isoformat()
                await send(message)
            
            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)

# ============= Main =============

async def initialize_gateway(config_file: str = ""):
    """Initialize the gateway on startup"""
    await load_child_servers(config_file)
    logger.info(f"Gateway initialized with {len(state.child_servers)} child servers")

def main() -> int:
    import sys
    import uvicorn
    import argparse

    arg_parser = argparse.ArgumentParser(description="MCP Gateway Server")
    arg_parser.add_argument("port", type=int, nargs='?', default=8001, help="Port to run the gateway server on")
    arg_parser.add_argument("--no_http", action="store_true", help="Disable HTTP server (for use in Github Copilot)")
    arg_parser.add_argument("--config", type=str, default="", help="Path to gateway configuration JSON file")
    args = arg_parser.parse_args()
    
    # Get port from command line argument or use default
    port_number = args.port
    try: 
        port = int(port_number)
    except ValueError:
        print(f"Invalid port number: {port_number}")
        print("Usage: gateway_server.py [port]")
        sys.exit(1)
    
    # Run initialization
    asyncio.run(initialize_gateway(args.config))
    
    if not args.no_http:

        # Define middleware
        custom_middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],  # Allow all origins for development
                allow_credentials=True,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["*"],
                expose_headers=["mcp-session-id", "Mcp-Session-Id", "*"]
            ),
            Middleware(LoggingMiddleware),
        ]
        
        # Create ASGI app with middleware
        http_app = gateway.http_app(
            path="/mcp",
            middleware=custom_middleware
        )
        
        # Run the server
        print("Starting MCP Gateway Server...")
        print(f"Gateway available at: http://localhost:{port}")
        print(f"Health check at: http://localhost:{port}/health")
        print(f"Status at: http://localhost:{port}/status")
        print(f"MCP endpoint at: http://localhost:{port}/mcp")
        print("Press Ctrl+C to stop the server")
    
        try:
            uvicorn.run(http_app, host="0.0.0.0", port=port)
        except KeyboardInterrupt:
            print("\nGateway server stopped.")
    else:
        try:
            gateway.run()
        except KeyboardInterrupt:
            print("\nGateway server stopped.")

    return 0

if __name__ == "__main__":
    sys.exit(main())