# di-mcpserver
Model Context Protocol (MCP) server implementation using FastMCP v2 with HTTP transport for use with Document Intelligence

## Architecture

```mermaid
graph TB
    subgraph "Bosch Private Cloud"
        Backend[Document Intelligence Backend]
    end

    subgraph "User's Local Machine"
        subgraph "Client/Browser"
            UI[Document Intelligence]
        end
        MCPServer[MCP Server]
        FileSystem[File System<br/>Documents]
        LocalApps[Local Applications]
        
        MCPServer <--> FileSystem
        MCPServer <--> LocalApps
    end
    
    subgraph "Cloud/Hyperscaler"
        LLM[LLM Model]
    end
    
    UI <-->|HTTPS| Backend
    Backend <-->|API| LLM
    UI <--> MCPServer
    
    style UI fill:#e1f5fe
    style MCPServer fill:#fff3e0
    style Backend fill:#e8f5e9
    style LLM fill:#f3e5f5
    style FileSystem fill:#f5f5f5
    style LocalApps fill:#f5f5f5
```

## Implementation Guide
While MCP server are exptected to implement the standard streaming-http interface (SSE has been deprected from the MCP standard) browser security requires a relaxed CORS policy. Please see the demo server for a reference implementation.

