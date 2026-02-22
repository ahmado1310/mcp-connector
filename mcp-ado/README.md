# MCP Azure DevOps Server

A Model Context Protocol (MCP) server for Azure DevOps integration.

> **Note:** Installation and configuration details are in the [Root README](../README.md)

## Description

This MCP server provides comprehensive access to Azure DevOps via the REST API. It enables managing work items, browsing repositories, monitoring build pipelines, and performing code searches - all through the standardized MCP protocol.

## Features

- ✅ **Work Items**: List, details, create and update work items
- ✅ **Repositories**: Repository overview and commit history
- ✅ **Builds**: Build pipeline queries and detailed build information
- ✅ **Pull Requests**: PR management and review processes
- ✅ **Code Search**: Full-text search across all repositories
- ✅ **WIQL**: Advanced work item queries with Work Item Query Language
- ✅ **HTTP Transport**: Streaming HTTP via FastMCP v2
- ✅ **CORS Support**: Browser-based access enabled

## Endpoint

- **Port**: 8003
- **URL**: `http://localhost:8003/mcp`
- **Health Check**: `http://localhost:8003/healthcheck`

## Tools

### Work Items
  
- `list_work_items` - Query work items using WIQL
- `get_work_item` - Get details of a work item

### Repositories

- `list_repositories` - List all Git repositories in a project
- `get_repository_commits` - Get recent commits from a repository
- `list_pull_requests` - List pull requests (active, completed, or all)

### Builds

- `list_builds` - List builds with status filter
- `get_build_details` - Get detailed build information

### Code Search

- `search_code` - Volltextsuche über alle Repositories

## Weitere Informationen

Detaillierte API-Dokumentation und Beispiele finden Sie in der [Azure DevOps REST API Reference](https://learn.microsoft.com/en-us/rest/api/azure/devops/).
