#!/usr/bin/env python3
"""
HTTP/SSE Server runner for TastyTrade MCP Server.

This script exposes the MCP server over HTTP using Server-Sent Events (SSE),
allowing external agents to connect to the MCP server via HTTP instead of stdio.
"""

import argparse
import logging
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for MCP HTTP/SSE server."""
    parser = argparse.ArgumentParser(
        description="TastyTrade MCP Server with HTTP/SSE Transport",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables Required:
  TASTYTRADE_CLIENT_SECRET    OAuth client secret
  TASTYTRADE_REFRESH_TOKEN    OAuth refresh token
  TASTYTRADE_ACCOUNT_ID       (Optional) Specific account ID to use

Examples:
  # Start on default port 8000
  python -m tasty_agent.http_server

  # Start on custom port with specific host
  python -m tasty_agent.http_server --host 127.0.0.1 --port 8080

  # Enable debug logging
  python -m tasty_agent.http_server --debug

Connect to the server:
  # MCP client connection URL
  http://localhost:8000/sse

  # Using MCP Inspector
  npx @modelcontextprotocol/inspector http://localhost:8000/sse
        """
    )

    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # Validate environment variables
    if not os.getenv("TASTYTRADE_CLIENT_SECRET") or not os.getenv("TASTYTRADE_REFRESH_TOKEN"):
        logger.error("Missing required environment variables!")
        logger.error("Please set TASTYTRADE_CLIENT_SECRET and TASTYTRADE_REFRESH_TOKEN")
        sys.exit(1)

    # Import and run MCP server with SSE transport
    try:
        # Set environment variables for FastMCP to use custom host/port
        # Note: FastMCP reads these when creating the Starlette app
        os.environ['FASTMCP_HOST'] = args.host
        os.environ['FASTMCP_PORT'] = str(args.port)

        from tasty_agent.server import mcp_app

        logger.info("Starting TastyTrade MCP Server with HTTP/SSE transport...")
        logger.info(f"MCP Endpoint: http://{args.host}:{args.port}/sse")
        logger.info("Connect your MCP client to the endpoint above")

        # Note: FastMCP's host and port are set during initialization
        # Since mcp_app is already created, we need to override its settings
        mcp_app.host = args.host
        mcp_app.port = args.port

        # Run with SSE transport
        mcp_app.run(transport="sse")
    except ImportError as e:
        logger.error(f"Failed to import MCP server: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
