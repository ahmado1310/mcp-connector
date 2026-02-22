# MCP Confluence/Docupedia Server

A Model Context Protocol (MCP) server for Confluence/Docupedia integration.

> **Note:** Installation and configuration details are in the [Root README](../README.md)

## Description

This MCP server enables access to Confluence/Docupedia via the REST API. It supports search, page management, comments, attachments, and labels - optimized for enterprise environments with proxy support.

## Features

- ✅ **Content Search**: CQL (Confluence Query Language) support
- ✅ **Pages**: Create, read, and update pages
- ✅ **Spaces**: Space overview and details
- ✅ **Collaboration**: Comments, attachments, and labels
- ✅ **Proxy Support**: Corporate proxy support
- ✅ **SSL**: Optional SSL verification for internal CAs
- ✅ **HTTP Transport**: Streaming HTTP via FastMCP v2
- ✅ **CORS Support**: Browser-based access enabled

## Endpoint

- **Port**: 8004
- **URL**: `http://localhost:8004/mcp`
- **Health Check**: `http://localhost:8004/healthcheck`

## Available Tools

### Search & Discovery

- `search_content` - Content search with CQL
- `list_spaces` - List all accessible spaces
- `get_space` - Get space details
- `list_pages_in_space` - List all pages in a space

### Page Operations

- `get_page` - Get page by ID or title
- `get_page_children` - Get child pages

### Collaboration

- `get_page_comments` - Get comments on a page
- `get_page_attachments` - Get attachments
- `get_page_labels` - Get labels/tags

## Further Information

Detailed CQL query examples and API documentation can be found in the [Confluence REST API Reference](https://developer.atlassian.com/cloud/confluence/rest/).
space = "DOCS" AND text ~ "API"

-- Search by label
label = "important" AND type = page

-- Search by creator
creator = "john.doe" AND type = page

-- Search recent pages
type = page AND created >= now("-7d")

-- Combine multiple criteria
space = "DOCS" AND type = page AND label = "API" AND text ~ "REST"
```

## Troubleshooting

### Authentication Errors

- Verify your PAT or username/password is correct
- Check token hasn't expired
- Ensure you have access to the Confluence instance
- Try accessing Confluence in a browser first

### Proxy Issues

- Verify proxy URL is correct (`http://localhost:3128`)
- Check proxy is running (e.g., Px proxy for corporate networks)
- Try setting `disable_ssl_verification: true` if SSL errors occur
- Test proxy with curl: `curl -x http://localhost:3128 https://www.google.com`

### Connection Timeouts

- Check network connectivity to Confluence host
- Verify firewall rules allow connections
- Try increasing timeout in requests (modify `_make_confluence_request`)

### SSL Certificate Errors

- Set `disable_ssl_verification: true` in proxy config
- Install corporate CA certificate in Python's certificate store
- Use `requests.packages.urllib3.disable_warnings()` (already included)

### Page Not Found Errors

- Verify space key is correct (case-sensitive)
- Check you have permission to access the space/page
- Use `list_spaces` to see available spaces
- Use `list_pages_in_space` to browse available pages

## API Documentation

- [Confluence REST API Reference](https://developer.atlassian.com/cloud/confluence/rest/v1/intro/)
- [Confluence Query Language (CQL)](https://developer.atlassian.com/cloud/confluence/advanced-searching-using-cql/)
- [Confluence Storage Format](https://confluence.atlassian.com/doc/confluence-storage-format-790796544.html)

## Corporate Network Setup (Bosch Example)

For Bosch Docupedia access behind corporate proxy:

1. Install and configure Px proxy:
```bash
pip install px-proxy
px --proxy=rb-proxy-de.bosch.com:8080 --listen=127.0.0.1:3128
```

1. Set environment variables:

```powershell
$env:HTTP_PROXY = "http://localhost:3128"
$env:HTTPS_PROXY = "http://localhost:3128"
$env:NODE_TLS_REJECT_UNAUTHORIZED = "0"
```

1. Use configuration with proxy enabled and SSL verification disabled
