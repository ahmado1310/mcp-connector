# di-mcpserver

Model Context Protocol (MCP) server implementation using FastMCP v2 with HTTP transport for use with Document Intelligence

## Architecture

```mermaid
flowchart TB
    subgraph "Bosch Private Cloud"
        Backend["Document Intelligence Backend"]
    end

    subgraph "User Local Machine"
        subgraph "Client Browser"
            UI["Document Intelligence"]
        end

        Gateway["MCP Gateway"]
        AdoSrv["MCP ADO Server"]
        DocSrv["MCP Docupedia Server"]

        Gateway --> AdoSrv
        Gateway --> DocSrv
    end

    subgraph "Cloud Hyperscaler"
        LLM["LLM Model"]
    end

    UI <-->|"HTTPS"| Backend
    Backend <-->|"API"| LLM
    UI <--> Gateway

    style UI fill:#e1f5fe
    style Gateway fill:#fff3e0
    style AdoSrv fill:#fff3e0
    style DocSrv fill:#fff3e0
    style Backend fill:#e8f5e9
    style LLM fill:#f3e5f5
```

## Implementation Guide

While MCP server are exptected to implement the standard streaming-http interface (SSE has been deprected from the MCP standard) browser security requires a relaxed CORS policy. Please see the demo server for a reference implementation.
