# MCP Gateway Server

A gateway server for aggregating multiple Model Context Protocol (MCP) servers into a unified interface.

> **Note:** Installation and configuration details are in the [Root README](../README.md)

## Description

The MCP Gateway unifies multiple MCP servers into a single endpoint. Servers can be integrated as Python modules (optimal for performance) or as HTTP proxies (for external servers).

## Features

- ✅ **Multiple Server Types**: Module-based or HTTP proxy
- ✅ **Unified Interface**: One endpoint for all servers
- ✅ **Tool Namespacing**: Automatic prefixes prevent conflicts
- ✅ **Health Monitoring**: Built-in health monitoring
- ✅ **CORS Support**: Configurable for browser clients
- ✅ **Interactive UI**: Terminal UI for server monitoring
- ✅ **JSON Configuration**: Easy setup

## Endpoint

- **Port**: 8001
- **URL**: `http://localhost:8001/mcp`
- **For n8n**: `http://host.docker.internal:8001/mcp`

## Configuration

Edit [gateway_config.json](gateway_config.json) to configure MCP servers:

```json
{
  "gateway": {
    "name": "MCP Gateway Server",
    "cors": {
      "origins": ["*"],
      "credentials": true
    }
  },
  "child_servers": [
    {
      "name": "ADO Server",
      "type": "proxy",
      "url": "http://localhost:8003/mcp",
      "prefix": "ado",
      "description": "Azure DevOps Integration"
    },
    {
      "name": "Docupedia Server",
      "type": "proxy",
      "url": "http://localhost:8004/mcp",
      "prefix": "docupedia",
      "description": "Confluence/Docupedia Integration"
    }
  ]
}
```

### Server Types

**Module Servers** - Load Python modules directly (best performance):
```json
{
  "type": "module",
  "module_path": "path-to-module",
  "prefix": "unique-prefix"
}
```

**Proxy Servers** - External MCP servers via HTTP:
```json
{
  "type": "proxy",
  "url": "http://server-url/mcp",
  "prefix": "unique-prefix"
}
```

## Usage

The gateway is started via [start-all.ps1](../start-all.ps1) in the root directory.

## Further Information

The gateway aggregates all tools from connected servers and provides them under a single endpoint. Each tool automatically receives the configured prefix (e.g., `ado_list_work_items`, `docupedia_search_content`).

- `GET /` - Gateway status
- `GET /health` - Health check with server metrics
- `POST /mcp` - MCP protocol endpoint
- `GET /metrics` - Detailed metrics for all servers

### Using the Gateway Server with Github Copilot in VSCode

Add the following `mcp.json` file to the `.vscode` folder in the workspace you want to use the MCP gateway server in:
```json
{
  "servers": {
    "mcp-gateway": {
      "type": "http",
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

## Interactive UI

The gateway includes a terminal-based UI for monitoring:

```bash
uv run ui.py
```

Features:
- Real-time server status monitoring
- Request/error metrics
- Connection health indicators
- Automatic refresh every 5 seconds

## Architecture

The gateway acts as a central hub, routing MCP requests to appropriate backend servers:

1. **Request Reception**: Receives MCP protocol requests on `/mcp`
2. **Tool Resolution**: Maps prefixed tool names to target servers
3. **Request Routing**: Forwards requests to the appropriate server
4. **Response Aggregation**: Combines responses from multiple servers
5. **Metrics Collection**: Tracks performance and health metrics

## Monitoring

### Health Check
```bash
curl http://localhost:8002/health
```

Response:
```json
{
  "status": "healthy",
  "servers": {
    "demo": {
      "status": "connected",
      "type": "module"
    },
    "outlook": {
      "status": "connected",
      "type": "proxy"
    }
  }
}
```

### Metrics
```bash
curl http://localhost:8002/metrics
```

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   - Change the port using `--port` flag
   - Check for other services on port 8002

2. **Module Import Errors**
   - Ensure module is in Python path
   - Check module has proper `initialize()` function

3. **Proxy Connection Failed**
   - Verify external server is running
   - Check network connectivity
   - Validate health endpoint configuration

4. **Event Loop Errors**
   - The gateway handles async operations automatically
   - Ensure you're using the latest version