# MCP Connector – Deployment Diagram

Dieses Deployment-Diagramm zeigt die Laufzeitverteilung der Komponenten über Client, lokale Umgebung und externe Plattformen.

```mermaid
flowchart TB
    subgraph Client["Client Device"]
        MCPClient["MCP Client"]
    end

    subgraph LocalHost["Local Host"]
        Gateway["MCP Gateway\nHTTP /mcp\nPort 8001"]
        AdoServer["MCP ADO Server\nHTTP /mcp\nPort 8003"]
        DocServer["MCP Docupedia Server\nHTTP /mcp\nPort 8004"]
    end

    subgraph Azure["Azure DevOps Cloud"]
        AdoAPI["Azure DevOps REST API"]
    end

    subgraph Confluence["Confluence Cloud or On-Prem"]
        ConfAPI["Confluence REST API"]
    end

    MCPClient -->|"MCP over HTTP"| Gateway
    Gateway -->|"Prefixed tool routing"| AdoServer
    Gateway -->|"Prefixed tool routing"| DocServer

    AdoServer -->|"HTTPS REST"| AdoAPI
    DocServer -->|"HTTPS REST"| ConfAPI
```

## Hinweise

- Gateway aggregiert beide MCP-Server und stellt einen zentralen MCP-Einstieg bereit.
- ADO- und Docupedia-Server sind als getrennte Deployments mit eigenen Ports dargestellt.
- Externe APIs sind als eigene Deployments außerhalb des lokalen Hosts modelliert.
