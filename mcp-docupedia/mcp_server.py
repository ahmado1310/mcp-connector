#!/usr/bin/env python3
"""
MCP Confluence/Docupedia Server using FastMCP v2 with HTTP transport
Features:
- Confluence REST API integration for Docupedia
- Page, space, and content search
- Page creation and updates
- Proxy support for corporate networks
- CORS enabled for browser access
- Request/response logging for debugging
- Full MCP protocol support with Confluence tools
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
from urllib.parse import quote
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
confluence_config = None

def _load_config():
    """Load Confluence configuration"""
    global confluence_config
    
    if confluence_config is not None:
        return confluence_config
    
    # Load configuration file
    config_path = os.getenv('MCP_CONFLUENCE_CONFIG', 'config.json')
    
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
            confluence_config = json.load(f)
        logger.info("Confluence configuration loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        confluence_config = {}
    
    return confluence_config

def _get_auth_header():
    """Get authentication header for Confluence API"""
    config = _load_config()
    
    # Try PAT first (Personal Access Token)
    pat = config.get('confluence', {}).get('api_token')
    
    # Expand environment variable if it's in ${VAR} format
    if pat and pat.startswith('${') and pat.endswith('}'):
        var_name = pat[2:-1]  # Extract variable name from ${VAR}
        pat = os.getenv(var_name)
        logger.info(f"Expanded API token from environment variable: {var_name}")
    
    # Fallback to direct environment variable
    if not pat:
        pat = os.getenv('CONFLUENCE_API_TOKEN')
    
    if pat:
        logger.info(f"Using API token: {pat[:10]}... (length: {len(pat)})")
        # For Confluence Cloud/DC with PAT
        encoded_auth = base64.b64encode(f":{pat}".encode()).decode()
        return {"Authorization": f"Bearer {pat}"}
    
    # Fall back to username/password
    username = config.get('confluence', {}).get('username') or os.getenv('CONFLUENCE_USERNAME')
    password = config.get('confluence', {}).get('password') or os.getenv('CONFLUENCE_PASSWORD')
    
    if username and password:
        encoded_auth = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {encoded_auth}"}
    
    raise ValueError("Confluence authentication not configured (PAT or username/password required)")

def _get_session():
    """Get requests session with proxy configuration"""
    session = requests.Session()
    
    config = _load_config()
    proxy_config = config.get('proxy', {})
    
    if proxy_config.get('enabled'):
        proxy_url = proxy_config.get('url', 'http://localhost:3128')
        session.proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        # Disable SSL verification if configured
        if proxy_config.get('disable_ssl_verification'):
            session.verify = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    return session

def _make_confluence_request(
    endpoint: str,
    method: str = "GET",
    body: Optional[Dict] = None,
    params: Optional[Dict] = None
) -> Dict[str, Any]:
    """Make a request to Confluence REST API"""
    config = _load_config()
    base_url = config.get('confluence', {}).get('host', '').rstrip('/')
    
    if not base_url:
        raise ValueError("Confluence host not configured")
    
    # Ensure base_url includes protocol
    if not base_url.startswith(('http://', 'https://')):
        base_url = f"https://{base_url}"
    
    # Build full URL
    url = f"{base_url}/rest/api/{endpoint}"
    
    headers = _get_auth_header()
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "application/json"
    
    session = _get_session()
    
    if method == "GET":
        response = session.get(url, headers=headers, params=params)
    elif method == "POST":
        response = session.post(url, headers=headers, json=body, params=params)
    elif method == "PUT":
        response = session.put(url, headers=headers, json=body, params=params)
    elif method == "DELETE":
        response = session.delete(url, headers=headers, params=params)
    else:
        raise ValueError(f"Unsupported method: {method}")
    
    response.raise_for_status()
    
    # Handle empty responses
    if response.status_code == 204 or not response.content:
        return {}
    
    return response.json()

# Initialize on module load for standalone mode
if __name__ == "__main__" or os.getenv('MCP_STANDALONE'):
    _load_config()

# Initialize the MCP server
mcp = FastMCP("Confluence/Docupedia MCP Server")

# ============= Health Check Route =============

@mcp.custom_route("/", methods=["GET"])
@mcp.custom_route("/healthcheck", methods=["GET"])
def healthcheck(request: Request) -> PlainTextResponse:
    """Health check endpoint for the MCP server"""
    config_status = "configured" if confluence_config else "not configured"
    return PlainTextResponse(f"Confluence/Docupedia MCP Server is running (Config: {config_status})")

# ============= Confluence Tools =============
# NOTE: Tools marked as "Official" are available in the official @atlassian-dc-mcp/confluence npm package
# Tools marked as "Custom" are self-implemented extensions not available in the official package

# ============= Official Confluence Tools (also in @atlassian-dc-mcp/confluence) =============

@mcp.tool
def search_content(
    query: str,
    space_key: Optional[str] = None,
    content_type: Optional[str] = None,
    max_results: Optional[int] = None
) -> Dict[str, Any]:
    """
    Search for content in Confluence using CQL (Confluence Query Language)
    
    Args:
        query: Search query text (will be automatically quoted if not already in CQL format)
        space_key: Limit search to specific space (optional, defaults to 'CONLP')
        content_type: Type of content to search (page, blogpost, comment, attachment) - defaults from config
        max_results: Maximum number of results to return - defaults from config
    
    Returns:
        Search results with page details
    """
    config = _load_config()
    
    # Get defaults from config if not provided
    if space_key is None:
        space_key = config.get('confluence', {}).get('default_space', 'CONLP')
    
    if content_type is None:
        content_type = config.get('search_defaults', {}).get('content_type', 'page')
    
    if max_results is None:
        max_results = config.get('search_defaults', {}).get('max_results', 25)
    
    # Build CQL query - only quote if query doesn't already contain quotes or CQL operators
    if '"' in query or ' OR ' in query or ' AND ' in query or query.strip().startswith('text'):
        # Query already contains CQL syntax, use as-is
        text_query = query
    else:
        # Simple text query, wrap in quotes
        text_query = f'"{query}"'
    
    # Build CQL query parts
    cql_parts = [f'text ~ {text_query}', f'type = {content_type}']
    
    if space_key:
        cql_parts.append(f'space = "{space_key}"')
    
    cql = " AND ".join(cql_parts)
    
    params = {
        "cql": cql,
        "limit": max_results,
        "expand": "content.space,content.version,content.body.view"
    }
    
    return _make_confluence_request("content/search", params=params)

@mcp.tool
def get_page(
    page_id: Optional[str] = None,
    page_title: Optional[str] = None,
    space_key: Optional[str] = None,
    expand: str = "body.storage,version,space"
) -> Dict[str, Any]:
    """
    Get a Confluence page by ID or title
    
    Args:
        page_id: Page ID (if known)
        page_title: Page title (requires space_key)
        space_key: Space key (required if using page_title)
        expand: Comma-separated list of properties to expand
    
    Returns:
        Page content and metadata
    """
    if page_id:
        return _make_confluence_request(f"content/{page_id}", params={"expand": expand})
    elif page_title and space_key:
        params = {
            "spaceKey": space_key,
            "title": page_title,
            "expand": expand
        }
        data = _make_confluence_request("content", params=params)
        
        # Extract first result if found
        if data.get("results"):
            return data["results"][0]
        else:
            raise ValueError("Page not found")
    else:
        raise ValueError("Either page_id or both page_title and space_key are required")

@mcp.tool
def list_spaces(
    max_results: Optional[int] = None,
    space_type: str = "global"
) -> Dict[str, Any]:
    """
    List Confluence spaces
    
    Args:
        max_results: Maximum number of spaces to return (defaults from config)
        space_type: Type of spaces to list (global, personal)
    
    Returns:
        List of spaces
    """
    # Get default max_results from config if not provided
    if max_results is None:
        config = _load_config()
        max_results = config.get('search_defaults', {}).get('max_results', 25)
    
    params = {
        "limit": max_results,
        "type": space_type,
        "expand": "description.plain,homepage"
    }
    
    return _make_confluence_request("space", params=params)

# ============= Custom Confluence Tools (self-implemented extensions) =============

@mcp.tool
def get_space(
    space_key: str,
    expand: str = "description.plain,homepage"
) -> Dict[str, Any]:
    """
    Get details of a specific Confluence space
    
    Args:
        space_key: Space key
        expand: Comma-separated list of properties to expand
    
    Returns:
        Space details
    """
    params = {"expand": expand}
    return _make_confluence_request(f"space/{space_key}", params=params)

@mcp.tool
def list_pages_in_space(
    space_key: str,
    max_results: Optional[int] = None,
    expand: str = "version,space"
) -> Dict[str, Any]:
    """
    List all pages in a Confluence space
    
    Args:
        space_key: Space key
        max_results: Maximum number of pages to return (defaults from config)
        expand: Comma-separated list of properties to expand
    
    Returns:
        List of pages in the space
    """
    # Get default max_results from config if not provided
    if max_results is None:
        config = _load_config()
        max_results = config.get('search_defaults', {}).get('max_results', 25)
    
    params = {
        "spaceKey": space_key,
        "limit": max_results,
        "expand": expand,
        "type": "page"
    }
    
    return _make_confluence_request("content", params=params)

@mcp.tool
def get_page_children(
    page_id: str,
    expand: str = "version,space"
) -> Dict[str, Any]:
    """
    Get child pages of a specific page
    
    Args:
        page_id: Parent page ID
        expand: Comma-separated list of properties to expand
    
    Returns:
        List of child pages
    """
    params = {"expand": expand}
    return _make_confluence_request(f"content/{page_id}/child/page", params=params)

@mcp.tool
def get_page_attachments(
    page_id: str,
    max_results: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get attachments for a specific page
    
    Args:
        page_id: Page ID
        max_results: Maximum number of attachments to return (defaults from config)
    
    Returns:
        List of attachments
    """
    # Get default max_results from config if not provided
    if max_results is None:
        config = _load_config()
        max_results = config.get('search_defaults', {}).get('max_results', 25)
    
    params = {
        "limit": max_results,
        "expand": "version"
    }
    
    return _make_confluence_request(f"content/{page_id}/child/attachment", params=params)

@mcp.tool
def get_page_comments(
    page_id: str,
    max_results: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get comments for a specific page
    
    Args:
        page_id: Page ID
        max_results: Maximum number of comments to return (defaults from config)
    
    Returns:
        List of comments
    """
    # Get default max_results from config if not provided
    if max_results is None:
        config = _load_config()
        max_results = config.get('search_defaults', {}).get('max_results', 25)
    
    params = {
        "limit": max_results,
        "expand": "body.view,version"
    }
    
    return _make_confluence_request(f"content/{page_id}/child/comment", params=params)

@mcp.tool
def get_page_labels(
    page_id: str
) -> Dict[str, Any]:
    """
    Get labels/tags for a specific page
    
    Args:
        page_id: Page ID
    
    Returns:
        List of labels
    """
    return _make_confluence_request(f"content/{page_id}/label")

# ============= Resources =============

@mcp.resource("confluence://config")
def get_confluence_config() -> str:
    """Get Confluence server configuration"""
    config = _load_config()
    safe_config = {
        "host": config.get('confluence', {}).get('host', 'Not configured'),
        "proxy_enabled": config.get('proxy', {}).get('enabled', False),
        "api_version": "Latest"
    }
    return json.dumps(safe_config, indent=2)

@mcp.resource("confluence://spaces")
def list_all_spaces() -> str:
    """List all accessible Confluence spaces"""
    try:
        data = _make_confluence_request("space", params={"limit": 100})
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

# ============= Prompts =============

@mcp.prompt
def page_summary_prompt(page_id: str) -> List[Dict[str, Any]]:
    """Generate prompts for summarizing a Confluence page"""
    return [
        {
            "role": "user",
            "content": f"Summarize the Confluence page with ID {page_id}. Include key points, main topics, and important information."
        }
    ]

@mcp.prompt
def documentation_prompt(topic: str, space_key: str) -> List[Dict[str, Any]]:
    """Generate prompts for finding documentation on a topic"""
    return [
        {
            "role": "user",
            "content": f"Search for documentation about '{topic}' in Confluence space '{space_key}' and provide a comprehensive summary of the findings."
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
    logger.info("Confluence/Docupedia MCP Server initialized in module mode")
    return mcp

# ============= Main =============

def main():
    """Main entry point for running the server"""
    import uvicorn
    
    # Get port from environment or use default
    port = int(os.getenv('MCP_CONFLUENCE_PORT', '8004'))
    
    logger.info(f"Starting Confluence/Docupedia MCP Server on port {port}...")
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
