#!/usr/bin/env python3
"""
MCP Azure DevOps Server using FastMCP v2 with HTTP transport
Features:
- Azure DevOps REST API integration
- Work items, repositories, builds, and releases management
- CORS enabled for browser access
- Request/response logging for debugging
- Full MCP protocol support with ADO tools
"""

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from datetime import datetime
import json
from typing import Dict, List, Any, Optional
import logging
import os
from pathlib import Path
import base64
import requests
from dotenv import load_dotenv

# Load .env file from parent directory
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    logger = logging.getLogger(__name__)
    logger.info(f"Loaded .env from {env_path}")

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global configuration
ado_config = None

def _load_config():
    """Load Azure DevOps configuration"""
    global ado_config
    
    if ado_config is not None:
        return ado_config
    
    # Load configuration file
    config_path = os.getenv('MCP_ADO_CONFIG', 'config.json')
    
    # Handle relative paths for module mode
    if not Path(config_path).is_absolute():
        module_dir = Path(__file__).parent
        test_path = module_dir / config_path
        if test_path.exists():
            config_path = str(test_path)
        elif (module_dir / 'config.example.json').exists():
            config_path = str(module_dir / 'config.example.json')
    
    if not Path(config_path).exists() and Path('config.example.json').exists():
        logger.warning(f"Config file {config_path} not found, using config.example.json")
        config_path = 'config.example.json'
    
    try:
        with open(config_path, 'r') as f:
            ado_config = json.load(f)
        logger.info("Azure DevOps configuration loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        ado_config = {}
    
    return ado_config

def _get_auth_header():
    """Get authentication header for Azure DevOps API"""
    config = _load_config()
    pat = config.get('azure_devops', {}).get('pat')
    
    # Expand environment variable if it's in ${VAR} format
    if pat and pat.startswith('${') and pat.endswith('}'):
        var_name = pat[2:-1]  # Extract variable name from ${VAR}
        pat = os.getenv(var_name)
        logger.info(f"Expanded PAT from environment variable: {var_name}")
    
    # Fallback to direct environment variable
    if not pat:
        pat = os.getenv('AZURE_DEVOPS_PAT')
    
    if not pat:
        raise ValueError("Azure DevOps PAT not configured")
    
    logger.info(f"Using PAT: {pat[:10]}... (length: {len(pat)})")
    
    # Encode PAT for Basic authentication
    encoded_pat = base64.b64encode(f":{pat}".encode()).decode()
    return {"Authorization": f"Basic {encoded_pat}"}

def _make_ado_request(
    organization: str,
    project: str,
    endpoint: str,
    method: str = "GET",
    body: Optional[Dict] = None,
    api_version: str = "7.1"
) -> Dict[str, Any]:
    """Make a request to Azure DevOps REST API"""
    base_url = f"https://dev.azure.com/{organization}/{project}/_apis"
    
    # Check if endpoint already has query parameters
    separator = "&" if "?" in endpoint else "?"
    url = f"{base_url}/{endpoint}{separator}api-version={api_version}"
    
    headers = _get_auth_header()
    headers["Content-Type"] = "application/json"
    
    logger.info(f"ADO Request: {method} {url}")
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=body, timeout=30)
        elif method == "PATCH":
            response = requests.patch(url, headers=headers, json=body, timeout=30)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        logger.info(f"ADO Response: {response.status_code} ({len(response.content)} bytes)")
        
        # Check for non-2xx status codes
        if not response.ok:
            logger.error(f"ADO Error Response: {response.status_code}")
            logger.error(f"Response Headers: {dict(response.headers)}")
            logger.error(f"Response Body: {response.text[:500]}")
            
            # Provide more specific error messages based on status code
            if response.status_code == 404:
                # Extract the resource type from the URL for better error messages
                if "/items?path=" in url:
                    # Extract the path parameter for file not found errors
                    import re
                    path_match = re.search(r'path=([^&]+)', url)
                    path = path_match.group(1) if path_match else "unknown"
                    from urllib.parse import unquote
                    decoded_path = unquote(path)
                    raise ValueError(
                        f"File or path not found in repository: {decoded_path}. "
                        f"Please verify the path exists in the repository."
                    )
                else:
                    raise ValueError(
                        f"Resource not found (404). URL: {url}. "
                        f"Please verify the resource exists and you have access to it."
                    )
            elif response.status_code == 401:
                raise ValueError(
                    "Authentication failed (401). Please check your Personal Access Token (PAT) is valid."
                )
            elif response.status_code == 403:
                raise ValueError(
                    "Access forbidden (403). Please verify you have permission to access this resource."
                )
            else:
                # For other errors, raise the original HTTP error
                response.raise_for_status()
        
        # Try to parse JSON response
        try:
            return response.json()
        except requests.exceptions.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response")
            logger.error(f"Content-Type: {response.headers.get('Content-Type', 'unknown')}")
            logger.error(f"Response Text (first 1000 chars): {response.text[:1000]}")
            raise ValueError(
                f"Azure DevOps API returned non-JSON response. "
                f"Status: {response.status_code}, "
                f"Content-Type: {response.headers.get('Content-Type', 'unknown')}, "
                f"Body preview: {response.text[:200]}"
            ) from e
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        # Don't wrap ValueError that we already raised above
        if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
            # HTTPError already handled above, re-raise as is
            raise
        raise ValueError(f"Failed to connect to Azure DevOps: {e}") from e

# Initialize on module load for standalone mode
if __name__ == "__main__" or os.getenv('MCP_STANDALONE'):
    _load_config()

# Initialize the MCP server
mcp = FastMCP("Azure DevOps MCP Server")

# ============= Health Check Route =============

@mcp.custom_route("/", methods=["GET"])
@mcp.custom_route("/healthcheck", methods=["GET"])
def healthcheck(request: Request) -> PlainTextResponse:
    """Health check endpoint for the MCP server"""
    config_status = "configured" if ado_config else "not configured"
    return PlainTextResponse(f"Azure DevOps MCP Server is running (Config: {config_status})")

# ============= Azure DevOps Tools =============

@mcp.tool
def list_work_items(
    organization: Optional[str] = None,
    project: Optional[str] = None,
    wiql_query: Optional[str] = None,
    max_results: int = 50
) -> Dict[str, Any]:
    """
    List work items from Azure DevOps using WIQL query
    
    Args:
        organization: Azure DevOps organization name (defaults to config)
        project: Project name (defaults to config)
        wiql_query: WIQL query (default: returns recent items)
        max_results: Maximum number of results to return
    
    Returns:
        List of work items matching the query
    """
    config = _load_config()
    if organization is None:
        organization = config.get('azure_devops', {}).get('organization')
    if project is None:
        project = config.get('azure_devops', {}).get('default_project')
    
    if not organization or not project:
        raise ValueError("Organization and project must be provided or configured")
    
    if not wiql_query:
        # Default query - limit will be applied via API parameter
        wiql_query = f"SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.TeamProject] = '{project}' ORDER BY [System.ChangedDate] DESC"
    
    # Execute WIQL query with $top parameter to limit results
    wiql_body = {"query": wiql_query}
    
    # Add $top parameter to the endpoint to avoid exceeding 20,000 item limit
    endpoint = f"wit/wiql?$top={max_results}"
    data = _make_ado_request(organization, project, endpoint, method="POST", body=wiql_body)
    
    work_item_refs = data.get("workItems", [])[:max_results]
    
    if not work_item_refs:
        return {"work_items": [], "count": 0}
    
    # Get work item IDs
    ids = [str(item["id"]) for item in work_item_refs]
    ids_param = ",".join(ids)
    
    # Fetch full work item details
    details_data = _make_ado_request(
        organization,
        project,
        f"wit/workitems?ids={ids_param}&$expand=all"
    )
    
    work_items = details_data.get("value", [])
    
    return {
        "work_items": work_items,
        "count": len(work_items)
    }

@mcp.tool
def get_work_item(
    work_item_id: int,
    organization: Optional[str] = None,
    project: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get details of a specific work item
    
    Args:
        work_item_id: Work item ID
        organization: Azure DevOps organization name (defaults to config)
        project: Project name (defaults to config)
    
    Returns:
        Work item details
    """
    config = _load_config()
    if organization is None:
        organization = config.get('azure_devops', {}).get('organization')
    if project is None:
        project = config.get('azure_devops', {}).get('default_project')
    
    if not organization or not project:
        raise ValueError("Organization and project must be provided or configured")
        
    return _make_ado_request(
        organization,
        project,
        f"wit/workitems/{work_item_id}?$expand=all"
    )


@mcp.tool
def list_repositories(
    organization: Optional[str] = None,
    project: Optional[str] = None
) -> Dict[str, Any]:
    """
    List all Git repositories in a project
    
    Args:
        organization: Azure DevOps organization name (defaults to config)
        project: Project name (defaults to config)
    
    Returns:
        List of repositories
    """
    config = _load_config()
    if organization is None:
        organization = config.get('azure_devops', {}).get('organization')
    if project is None:
        project = config.get('azure_devops', {}).get('default_project')
    
    if not organization or not project:
        raise ValueError("Organization and project must be provided or configured")
        
    return _make_ado_request(organization, project, "git/repositories")

@mcp.tool
def get_repository_commits(
    repository_id: str,
    max_results: int = 20,
    organization: Optional[str] = None,
    project: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get recent commits from a repository
    
    Args:
        repository_id: Repository ID or name
        max_results: Maximum number of commits to return
        organization: Azure DevOps organization name (defaults to config)
        project: Project name (defaults to config)
    
    Returns:
        List of commits
    """
    config = _load_config()
    if organization is None:
        organization = config.get('azure_devops', {}).get('organization')
    if project is None:
        project = config.get('azure_devops', {}).get('default_project')
    
    if not organization or not project:
        raise ValueError("Organization and project must be provided or configured")
        
    return _make_ado_request(
        organization,
        project,
        f"git/repositories/{repository_id}/commits?$top={max_results}"
    )

@mcp.tool
def list_builds(
    max_results: int = 20,
    status_filter: Optional[str] = None,
    organization: Optional[str] = None,
    project: Optional[str] = None
) -> Dict[str, Any]:
    """
    List build pipelines and recent builds
    
    Args:
        max_results: Maximum number of builds to return
        status_filter: Filter by status (e.g., 'completed', 'inProgress')
        organization: Azure DevOps organization name (defaults to config)
        project: Project name (defaults to config)
    
    Returns:
        List of builds
    """
    config = _load_config()
    if organization is None:
        organization = config.get('azure_devops', {}).get('organization')
    if project is None:
        project = config.get('azure_devops', {}).get('default_project')
    
    if not organization or not project:
        raise ValueError("Organization and project must be provided or configured")
        
    endpoint = f"build/builds?$top={max_results}"
    if status_filter:
        endpoint += f"&statusFilter={status_filter}"
    
    return _make_ado_request(organization, project, endpoint)

@mcp.tool
def get_build_details(
    build_id: int,
    organization: Optional[str] = None,
    project: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get detailed information about a specific build
    
    Args:
        build_id: Build ID
        organization: Azure DevOps organization name (defaults to config)
        project: Project name (defaults to config)
    
    Returns:
        Build details including logs
    """
    config = _load_config()
    if organization is None:
        organization = config.get('azure_devops', {}).get('organization')
    if project is None:
        project = config.get('azure_devops', {}).get('default_project')
    
    if not organization or not project:
        raise ValueError("Organization and project must be provided or configured")
        
    return _make_ado_request(organization, project, f"build/builds/{build_id}")

@mcp.tool
def list_pull_requests(
    repository_id: str,
    status: str = "active",
    organization: Optional[str] = None,
    project: Optional[str] = None
) -> Dict[str, Any]:
    """
    List pull requests in a repository
    
    Args:
        repository_id: Repository ID or name
        status: PR status ('active', 'completed', 'abandoned', 'all')
        organization: Azure DevOps organization name (defaults to config)
        project: Project name (defaults to config)
    
    Returns:
        List of pull requests
    """
    config = _load_config()
    if organization is None:
        organization = config.get('azure_devops', {}).get('organization')
    if project is None:
        project = config.get('azure_devops', {}).get('default_project')
    
    if not organization or not project:
        raise ValueError("Organization and project must be provided or configured")
        
    return _make_ado_request(
        organization,
        project,
        f"git/repositories/{repository_id}/pullrequests?searchCriteria.status={status}"
    )

@mcp.tool
def search_code(
    search_text: str,
    max_results: int = 50,
    organization: Optional[str] = None,
    project: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search for code across repositories in the project
    
    Args:
        search_text: Text to search for
        max_results: Maximum number of results
        organization: Azure DevOps organization name (defaults to config)
        project: Project name (defaults to config)
    
    Returns:
        Search results
    """
    config = _load_config()
    if organization is None:
        organization = config.get('azure_devops', {}).get('organization')
    if project is None:
        project = config.get('azure_devops', {}).get('default_project')
    
    if not organization or not project:
        raise ValueError("Organization and project must be provided or configured")
        
    url = f"https://almsearch.dev.azure.com/{organization}/{project}/_apis/search/codesearchresults?api-version=7.1-preview.1"
    
    headers = _get_auth_header()
    headers["Content-Type"] = "application/json"
    
    body = {
        "searchText": search_text,
        "$top": max_results
    }
    
    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()
    
    return response.json()

@mcp.tool
def get_repository_item(
    repository_id: str,
    path: str,
    organization: Optional[str] = None,
    project: Optional[str] = None,
    include_content: bool = True
) -> Dict[str, Any]:
    """
    Fetch a file (item) from an ADO Git repository by path.
    Returns JSON metadata and content (if include_content=True).
    
    Args:
        repository_id: Repository ID or name
        path: File path (e.g., '/docs/src/stock_management/modules/introduction/pages/introduction.adoc')
               Must start with '/' and be the full path from repository root
        organization: Azure DevOps organization name (defaults to config)
        project: Project name (defaults to config)
        include_content: Whether to include file content in response
    
    Returns:
        File metadata and content
    
    Raises:
        ValueError: If the file is not found (404) or path is invalid
    
    Note:
        - The path is case-sensitive
        - Use forward slashes (/) for path separators
        - Verify the file exists in the repository before calling
    """
    config = _load_config()
    if organization is None:
        organization = config.get('azure_devops', {}).get('organization')
    if project is None:
        project = config.get('azure_devops', {}).get('default_project')
    
    if not organization or not project:
        raise ValueError("Organization and project must be provided or configured")
    
    # URL-encode the path parameter
    from urllib.parse import quote
    encoded_path = quote(path, safe='')
    
    endpoint = (
        f"git/repositories/{repository_id}/items"
        f"?path={encoded_path}&includeContent={'true' if include_content else 'false'}"
    )
    
    return _make_ado_request(organization, project, endpoint)

# ============= Resources =============

@mcp.resource("ado://config")
def get_ado_config() -> str:
    """Get Azure DevOps server configuration"""
    config = _load_config()
    safe_config = {
        "organization": config.get('azure_devops', {}).get('organization', 'Not configured'),
        "default_project": config.get('azure_devops', {}).get('default_project', 'Not configured'),
        "api_version": "7.1"
    }
    return json.dumps(safe_config, indent=2)

@mcp.resource("ado://projects/{organization}")
def list_projects(organization: str) -> str:
    """List all projects in an organization"""
    try:
        url = f"https://dev.azure.com/{organization}/_apis/projects?api-version=7.1"
        headers = _get_auth_header()
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

# ============= Prompts =============

@mcp.prompt
def work_item_analysis(work_item_id: int, organization: str, project: str) -> List[Dict[str, Any]]:
    """Generate prompts for analyzing a work item"""
    return [
        {
            "role": "user",
            "content": f"Analyze work item {work_item_id} in {organization}/{project} and provide insights about its status, blockers, and recommendations."
        }
    ]

@mcp.prompt
def pr_review_prompt(pr_id: int, organization: str, project: str, repository: str) -> List[Dict[str, Any]]:
    """Generate prompts for reviewing a pull request"""
    return [
        {
            "role": "user",
            "content": f"Review pull request {pr_id} in repository {repository} ({organization}/{project}). Focus on code quality, potential bugs, and adherence to best practices."
        }
    ]

# ============= Module Support =============

def get_middleware():
    """Get middleware configuration for the MCP server"""
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    
    middleware_list = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Allow all origins for development
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=["mcp-session-id", "Mcp-Session-Id", "*"]  # CRITICAL: Expose session ID header
        )
    ]
    
    return middleware_list

def initialize():
    """Initialize the server for module mode"""
    logger.info("Azure DevOps MCP Server initialized in module mode")
    return mcp

# ============= Main =============

def main():
    """Main entry point for running the server"""
    import uvicorn
    
    # Get port from environment or use default
    port = int(os.getenv('MCP_ADO_PORT', '8003'))
    
    logger.info(f"Starting Azure DevOps MCP Server on port {port}...")
    logger.info(f"Server will be available at: http://localhost:{port}/mcp")
    logger.info(f"Health check at: http://localhost:{port}/healthcheck")
    
    # Get middleware configuration
    custom_middleware = get_middleware()
    
    # Create ASGI app with CORS middleware
    http_app = mcp.http_app(
        path="/mcp",
        middleware=custom_middleware
    )
    
    # Run the server
    try:
        uvicorn.run(http_app, host="0.0.0.0", port=port)
    except KeyboardInterrupt:
        logger.info("Server stopped.")

if __name__ == "__main__":
    main()
