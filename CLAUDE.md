# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Model Context Protocol (MCP) server for TastyTrade brokerage accounts, enabling LLMs to monitor portfolios, analyze positions, and execute trades. It features AI-powered trade idea generation, automated IV analysis prompts, and built-in rate limiting to prevent API throttling.

## Commands

### Development & Testing

```bash
# Interactive testing with chat interface
uv run chat.py

# Debug with MCP inspector
npx @modelcontextprotocol/inspector uvx tasty-agent

# Install/run via uvx
uvx tasty-agent

# Run HTTP API server (for external agents)
uv run python -m tasty_agent.http_server
# or after install: tasty-agent-http

# Run background trading bot (one-time)
uv run background.py "Check my portfolio and rebalance if needed"

# Run background bot periodically
uv run background.py "Monitor SPY" --hourly
uv run background.py "Generate daily summary" --daily
uv run background.py "Scan opportunities" --period 1800  # 30 min

# Schedule bot for specific time (NYC timezone)
uv run background.py "Morning strategy" --schedule "9:30am" --hourly
uv run background.py "Buy the dip" --market-open --hourly
```

### Environment Configuration

Create a `.env` file with:
```
TASTYTRADE_CLIENT_SECRET=your_secret
TASTYTRADE_REFRESH_TOKEN=your_token
TASTYTRADE_ACCOUNT_ID=your_account_id  # Optional, defaults to first account
OPENAI_API_KEY=your_key  # For chat.py and background.py
MODEL_IDENTIFIER=provider:model_name  # Defaults to openai:gpt-4o-mini
```

## Architecture

### Core Components

**`tasty_agent/server.py`** - The main MCP server implementation containing:
- **Rate Limiting**: 2 requests/second via `AsyncLimiter` (line 44) to prevent API throttling
- **Session Management**:
  - OAuth session initialization in `lifespan()` (lines 75-110)
  - Automatic token refresh via `ensure_session_valid()` (lines 46-55) - checks expiration and refreshes if token expires within 1 minute
  - Session tokens last 15 minutes; refresh tokens never expire
- **Context System**: `ServerContext` dataclass holds session and account; `get_context()` (lines 69-73) ensures session validity before each tool call
- **Tool Categories**:
  - Account & Portfolio (lines 120-142): Balances, positions, NLV history
  - Market Data (lines 224-334): Quotes, Greeks, market metrics, streaming via DXLink
  - History (lines 340-404): Transaction and order history with pagination
  - Trading (lines 535-658): Multi-leg order placement, replacement, cancellation
  - Watchlists (lines 664-760): Public/private watchlist management
  - Analysis (lines 792-933): IV analysis prompts, AI-powered trade idea generation
- **Transport Support**: Supports both stdio (default) and HTTP/SSE transports via `mcp_app.run(transport="sse")`

**`tasty_agent/http_server.py`** - HTTP/SSE server CLI runner:
- Command-line interface for exposing MCP server over HTTP using SSE transport
- Configurable host and port (defaults to 0.0.0.0:8000)
- Environment variable validation
- Debug logging support
- Entry point: `tasty-agent-http` command (defined in pyproject.toml)
- MCP endpoint exposed at `/sse` for external agent connections

**`agent.py`** - Agent factory that creates pydantic-ai Agent instances with MCP server integration:
- Creates MCPServerStdio connection to the tasty-agent server
- Configures model via `MODEL_IDENTIFIER` env var
- Enables MCP sampling for server-side LLM calls

**`background.py`** - Automated trading bot with scheduling capabilities:
- Supports one-time and periodic execution (hourly, daily, custom intervals)
- NYC timezone scheduling with market hours awareness
- Market status checking to avoid running when markets are closed

**`chat.py`** - Interactive CLI for testing MCP tools during development

### Key Technical Details

**Order Placement Architecture** (`place_order` at line 634):
- Multi-leg support for complex options strategies (spreads, strangles, etc.)
- Automatic price discovery from real-time market quotes when no price specified
- Dry-run mode for testing without execution
- Price calculation via `calculate_net_price()` (line 587) uses mid-point of bid/ask

**Instrument Resolution** (`get_instrument_details` at line 272):
- Validates option parameters (strike, expiration, type)
- Caches option chains for 24 hours (line 266)
- Returns both streamer symbol and instrument object for downstream use

**Streaming Data** (DXLink):
- Used for real-time quotes and Greeks
- Handles out-of-order quote arrivals with dictionary collection
- Timeout-aware with configurable wait periods

**AI Trade Idea Generation** (`generate_trade_ideas` at line 884):
- Uses MCP sampling capability to make LLM calls from server
- Aggregates positions, watchlist symbols, and market metrics
- Creates comprehensive prompt with IV rank analysis and risk tolerance
- Returns actionable trade recommendations with specific strikes and expirations

### Important Implementation Notes

- All async tastytrade API calls use `a_*` prefix methods (e.g., `a_get_positions`)
- **Session refresh is automatic**: Every tool call checks token expiration via `get_context()` and refreshes if needed (within 1 minute of expiration)
- Rate limiter is critical - wrap any new API calls with `async with rate_limiter:`
- Order prices follow TastyTrade convention: negative for debits (buying), positive for credits (selling)
- Pagination is required for history APIs (transactions use 250/page, orders use 50/page)
- Option chain caching (24hr TTL) prevents excessive API calls for frequently-queried symbols
- The `to_table()` utility formats Pydantic models as plain text tables for LLM consumption
- Option instrument specs: always use YYYY-MM-DD for expiration dates
- Required instrument dict keys: `symbol`, `option_type` ('C'|'P'), `strike_price` (positive float), `expiration_date` (YYYY-MM-DD)
- Tools can call `await ctx.info(...)` to surface user-friendly messages to MCP clients
- Package entrypoint: `tasty-agent = "tasty_agent.server:mcp_app.run"` (defined in pyproject.toml)

### MCP Integration

This server is designed to be invoked via MCP clients (Claude Desktop, VS Code) with configuration:
```json
{
  "mcpServers": {
    "tastytrade": {
      "command": "uvx",
      "args": ["tasty-agent"],
      "env": {
        "TASTYTRADE_CLIENT_SECRET": "...",
        "TASTYTRADE_REFRESH_TOKEN": "...",
        "TASTYTRADE_ACCOUNT_ID": "..."
      }
    }
  },
  "capabilities": {
    "sampling": {}
  }
}
```

The `sampling` capability enables AI-powered trade analysis features (e.g., `generate_trade_ideas`).

### Example Tool Calls

```python
# Stock orders (auto-priced)
[{"symbol":"AAPL","action":"Buy","quantity":100}]

# Option spread
[
  {"symbol":"AAPL","option_type":"C","action":"Buy to Open","quantity":1,"strike_price":150.0,"expiration_date":"2024-12-20"},
  {"symbol":"AAPL","option_type":"C","action":"Sell to Open","quantity":1,"strike_price":155.0,"expiration_date":"2024-12-20"}
]

# Get quotes for stock and option
[
  {"symbol":"AAPL"},
  {"symbol":"TQQQ","option_type":"C","strike_price":100.0,"expiration_date":"2026-01-16"}
]
```

## Authentication Flow

1. Create OAuth app at https://my.tastytrade.com/app.html#/manage/api-access/oauth-applications
2. Enable all scopes and save client ID/secret
3. Create "New Personal OAuth Grant" with all scopes
4. Copy refresh token and configure via environment variables
5. Server initializes OAuth session in lifespan and selects account (by ID or defaults to first)
