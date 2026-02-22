# MCP Connector

A consolidated MCP Gateway system with Azure DevOps and Confluence/Docupedia integration.

## Overview

This project unifies three MCP servers in a shared environment:

- **[mcp-ado](mcp-ado/README.md)**: Azure DevOps MCP Server (Port 8003)
- **[mcp-docupedia](mcp-docupedia/README.md)**: Confluence/Docupedia MCP Server (Port 8004)
- **[mcp-gateway](mcp-gateway/README.md)**: Gateway and UI Dashboard (Port 8001)

## Prerequisites

- Python >= 3.12
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Installation

### 1. Clone Repository

```powershell
git clone <repository-url>
cd mcp-connector
```

### 2. Setup Virtual Environment

```powershell
# with uv
uv venv .venv

# Or with python
python -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1
```

your shell prompt should now show `(.venv)` indicating the virtual environment is active.

### 3. Install Dependencies

```powershell
# with uv
uv sync

# Or with pip please copy also the point (.)
pip install -e .
```

## Configuration

### Create .env File

Create a `.env` file in the root directory or you have `env.txt` file, just rename it to `.env` and fill in the required tokens.

```bash
# Azure DevOps
AZURE_DEVOPS_PAT=your-pat-token

# Confluence
CONFLUENCE_API_TOKEN=your-confluence-token

# Proxy Configuration
HTTP_PROXY=http://localhost:3128
HTTPS_PROXY=http://localhost:3128
http_proxy=http://localhost:3128
https_proxy=http://localhost:3128
NODE_TLS_REJECT_UNAUTHORIZED=0
```

### Azure DevOps (mcp-ado)

1. Copy the example configuration:

```powershell
Copy-Item mcp-ado\config.example.json mcp-ado\config.json
```

1. Edit `mcp-ado\config.json`:

```json
{
  "azure_devops": {
    "organization": "your-organization",
    "default_project": "your-project",
    "api_version": "7.1"
  }
}
```

**Creating a Personal Access Token (PAT):**

1. Go to `https://dev.azure.com/{your-organization}`
2. User Settings → Personal Access Tokens → "New Token"
3. Required Scopes:
   - Code: Read & Write
   - Work Items: Read & Write
   - Build: Read
   - Project and Team: Read
4. Copy token and paste into `.env`

### Confluence/Docupedia (mcp-docupedia)

1. Copy the example configuration:

```powershell
Copy-Item mcp-docupedia\config.example.json mcp-docupedia\config.json
```

2. Edit `mcp-docupedia\config.json`:

>`default_space`: Use your Confluence space key (e.g., "DOCUPEDIA")

>`max_results`: Maximum number of search results to return. This can be adjusted based on your needs. Depending how many results you want to give back per search to the AI model.
```json
{
  "confluence": {
    "host": "inside-docupedia.bosch.com/confluence",
    "default_space": "Your_Space_Key"
  },
  "proxy": {
    "enabled": true,
    "url": "http://localhost:3128",
    "disable_ssl_verification": true
  },
  "server": {
    "port": 8004,
    "host": "0.0.0.0"
  },
  "search_defaults": {
    "max_results": 30,
    "content_type": "page"
  }
}

```

**Creating a PAT:**

1. Log in to Confluence
2. Profile → Settings → Personal Access Tokens
3. "Create token" → Give it a name → Copy token
4. Paste token into `.env`

**Proxy Configuration:**

If you're behind a corporate proxy, set `enabled: true` and the correct proxy URL. Use `disable_ssl_verification: true` for self-signed certificates.

### Gateway (mcp-gateway)

Edit `mcp-gateway\gateway_config.json`:

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

## Usage

### Start All Services

**Option 1: Using Python Launcher**

```powershell
# Start MCP servers
uv run launcher.py

# In a separate terminal, start the Gateway UI
uv run mcp-gateway/ui.py
```

**Option 2: Using PowerShell Script (Separate Windows)**

```powershell
.\start-all.ps1
```

The servers:

- MCP ADO Server (Port 8003)
- MCP Docupedia Server (Port 8004)
- Gateway UI Dashboard (Port 8001)

**Stopping Services:**

Press `Ctrl+C` in the terminal to stop the launcher and all running servers.

### Start Individual Services

```powershell
# ADO Server
uv run mcp-ado/mcp_server.py

# Docupedia Server  
uv run mcp-docupedia/mcp_server.py

# Gateway UI
uv run mcp-gateway/ui.py
```

## Endpoints

| Service | Endpoint | Health Check |
| ------- | -------- | ------------ |
| MCP ADO Server | <http://localhost:8003/mcp> | <http://localhost:8003/healthcheck> |
| MCP Docupedia Server | <http://localhost:8004/mcp> | <http://localhost:8004/healthcheck> |
| Gateway | <http://localhost:8001/mcp> | <http://localhost:8001/health> |

## Project Structure

```text
mcp-connector/
├── .venv/                    # Shared virtual environment
├── .env                      # Environment variables (PATs, tokens)
├── env.txt                   # Environment template
├── pyproject.toml            # Central dependency management
├── uv.lock                   # Dependency lock file
├── setup.ps1                 # Setup script
├── launcher.py               # Unified launcher for all servers
├── start-all.ps1             # Start all services in separate windows
├── README.md                 # This file
├── docs/                     # Documentation and diagrams
├── mcp-ado/
│   ├── mcp_server.py         # ADO Server
│   ├── config.json           # ADO Configuration
│   └── README.md             # ADO Documentation
├── mcp-docupedia/
│   ├── mcp_server.py         # Docupedia Server
│   ├── config.json           # Confluence Configuration
│   └── README.md             # Docupedia Documentation
└── mcp-gateway/
    ├── gateway_server.py     # Gateway Server
    ├── ui.py                 # Terminal UI
    ├── gateway_config.json   # Gateway Configuration
    └── README.md             # Gateway Documentation
```

## Troubleshooting

### Installation Fails

- Ensure Python 3.12+ is installed: `python --version`
- Install uv: [uv installation](https://docs.astral.sh/uv/getting-started/installation/#standalone-installer)
- Run `.\setup.ps1` again

### Servers Won't Start

- Check if ports 8001, 8003, 8004 are free
- Verify configuration files for errors
- Check PAT tokens for validity

### Authentication Errors

- Verify PATs haven't expired
- Check required scopes/permissions
- Test connection manually in browser

### Proxy Issues

- Ensure proxy URL is correct
- For self-signed certificates: `disable_ssl_verification: true`
- Test with `$env:HTTP_PROXY = "http://localhost:3128"`

## Further Information

Detailed documentation for individual servers:

- [Azure DevOps Server](mcp-ado/README.md) - Tools, APIs and examples
- [Docupedia Server](mcp-docupedia/README.md) - CQL queries and Confluence API
- [Gateway Server](mcp-gateway/README.md) - Configuration and monitoring
