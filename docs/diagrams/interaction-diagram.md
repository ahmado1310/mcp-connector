# MCP Connector – Interaktionsdiagramm

Dieses Diagramm zeigt, wie ein Nutzer mit dem Werkzeug interagiert und wie Requests über Gateway und MCP-Server verarbeitet werden.

```mermaid
sequenceDiagram
    autonumber
    actor U as Nutzer
    participant C as Agent oder MCP Client
    participant G as MCP Gateway
    participant A as MCP ADO Server
    participant D as MCP Docupedia Server
    participant AZ as Azure DevOps API
    participant CF as Confluence API

    U->>C: Frage oder Arbeitsauftrag eingeben
    C->>G: initialize und tools/list
    G-->>C: verfügbare Tools mit Präfixen

    alt Aufgabe braucht Azure DevOps Daten
        C->>G: tools/call ado_tool
        G->>A: Weiterleitung an ADO Server
        A->>AZ: REST API Anfrage
        AZ-->>A: Antwortdaten
        A-->>G: Tool Ergebnis
        G-->>C: Ergebnis an Client
    else Aufgabe braucht Docupedia Daten
        C->>G: tools/call docupedia_tool
        G->>D: Weiterleitung an Docupedia Server
        D->>CF: REST API Anfrage
        CF-->>D: Antwortdaten
        D-->>G: Tool Ergebnis
        G-->>C: Ergebnis an Client
    end

    C-->>U: Antwort mit Evidenz und Zusammenfassung
```

## Hinweise

- Das Gateway ist der zentrale Einstiegspunkt für Tool-Calls.
- Die Auswahl des Zielservers erfolgt über den Tool-Präfix.
- Der Nutzer interagiert nur mit dem Client/Agent, nicht direkt mit den Backend-APIs.
