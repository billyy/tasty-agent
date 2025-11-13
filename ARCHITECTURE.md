# TastyTrade MCP Server Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER INTERACTION                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────┐         ┌────────────────┐      ┌──────────────────┐ │
│  │  Claude       │         │  chat.py       │      │  background.py   │ │
│  │  Desktop      │         │  (CLI)         │      │  (Scheduled Bot) │ │
│  │  (MCP Client) │         │                │      │                  │ │
│  └──────┬───────┘         └────────┬───────┘      └────────┬─────────┘ │
│         │                           │                        │           │
│         │ stdio/HTTP                │ stdio                  │ stdio     │
│         │                           │                        │           │
└─────────┼───────────────────────────┼────────────────────────┼───────────┘
          │                           │                        │
          │                           ▼                        │
          │                  ┌─────────────────┐              │
          │                  │   agent.py      │              │
          │                  │  (Pydantic-AI)  │◄─────────────┘
          │                  │                 │
          │                  │ • LLM Client    │
          │                  │ • Tool Calling  │
          │                  │ • System Prompt │
          │                  └────────┬────────┘
          │                           │
          │                           │ MCP Protocol
          │                           │ (stdio/subprocess)
          └───────────────────────────┼──────────────────────────────────┐
                                      │                                  │
┌─────────────────────────────────────┼──────────────────────────────────┤
│                          MCP SERVER LAYER                               │
├─────────────────────────────────────┼──────────────────────────────────┤
│                                     ▼                                   │
│                          ┌───────────────────┐                          │
│                          │  server.py        │                          │
│                          │  (FastMCP)        │                          │
│                          │                   │                          │
│                          │ Entry Points:     │                          │
│                          │  • stdio (default)│                          │
│                          │  • HTTP/SSE       │                          │
│                          └─────────┬─────────┘                          │
│                                    │                                    │
│                  ┌─────────────────┼─────────────────┐                  │
│                  │                 │                 │                  │
│         ┌────────▼────────┐ ┌─────▼──────┐ ┌───────▼────────┐          │
│         │ Session Mgmt    │ │ Tool Layer │ │ Rate Limiter   │          │
│         │                 │ │            │ │                │          │
│         │ • Token Refresh │ │ 20+ Tools  │ │ 5 req/sec      │          │
│         │ • Auto-refresh  │ │ • Account  │ │ (AsyncLimiter) │          │
│         │ • 15min TTL     │ │ • Trading  │ │                │          │
│         │ • 1min buffer   │ │ • Market   │ └────────────────┘          │
│         └─────────────────┘ │ • Watchlist│                              │
│                             │ • Analysis │                              │
│                             └────────────┘                              │
│                                    │                                    │
│              ┌─────────────────────┼─────────────────┐                  │
│              │                     │                 │                  │
│     ┌────────▼────────┐   ┌───────▼──────┐  ┌──────▼───────┐          │
│     │ Option Chain    │   │ DXLink       │  │ Instrument   │          │
│     │ Cache           │   │ Streamer     │  │ Resolution   │          │
│     │                 │   │              │  │              │          │
│     │ • 24hr TTL      │   │ • Real-time  │  │ • Validates  │          │
│     │ • aiocache      │   │ • Quotes     │  │ • Resolves   │          │
│     │ • Per symbol    │   │ • Greeks     │  │ • Caches     │          │
│     └─────────────────┘   └──────────────┘  └──────────────┘          │
│                                    │                                    │
└────────────────────────────────────┼────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────┐
│                       TASTYTRADE API LAYER                              │
├────────────────────────────────────┼────────────────────────────────────┤
│                                    ▼                                    │
│                        ┌────────────────────┐                           │
│                        │ tastytrade SDK     │                           │
│                        │ (v11.0.0)          │                           │
│                        │                    │                           │
│                        │ • Session          │                           │
│                        │ • Account          │                           │
│                        │ • DXLinkStreamer   │                           │
│                        │ • Instruments      │                           │
│                        │ • Orders           │                           │
│                        └──────────┬─────────┘                           │
│                                   │                                     │
│                                   │ HTTPS / WebSocket                   │
│                                   │                                     │
│                        ┌──────────▼─────────┐                           │
│                        │  TastyTrade API    │                           │
│                        │  api.tastyworks.com│                           │
│                        │                    │                           │
│                        │ • OAuth2           │                           │
│                        │ • REST API         │                           │
│                        │ • DXLink WS        │                           │
│                        └────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. User Interaction Layer

#### chat.py (CLI Client)
- Interactive command-line interface
- Uses pydantic-ai Agent
- Connects to MCP server via stdio
- Logging configured for clean output

#### agent.py (Pydantic-AI Agent Factory)
- Creates Agent instances
- Configures LLM (OpenAI, Claude, Groq, Ollama, etc.)
- Loads system prompt with trading rules
- Spawns MCP server as subprocess
- Manages conversation history

#### background.py (Automated Bot)
- Scheduled execution (hourly, daily, custom)
- Market hours awareness
- Uses same agent.py factory
- Runs autonomous trading tasks

#### Claude Desktop (MCP Client)
- Official Anthropic client
- Connects via stdio or HTTP/SSE
- Provides UI for tool interactions

### 2. MCP Server Layer (server.py)

#### Core Components

**FastMCP Application**
```python
mcp_app = FastMCP("TastyTrade", lifespan=lifespan)
```
- Entry point: `tasty-agent` command
- Transports: stdio (default), HTTP/SSE
- 20+ tools organized by category

**Session Management**
```python
async def ensure_session_valid(session: Session) -> None:
    # Checks expiration every tool call
    # Auto-refreshes 1 min before expiry
    if current_time >= session.session_expiration - timedelta(minutes=1):
        await session.a_refresh()
```

**Tool Categories:**

1. **Account & Portfolio** (3 tools)
   - `get_balances()` - Account balances
   - `get_positions()` - Current positions
   - `get_net_liquidating_value_history()` - Portfolio value over time

2. **Market Data** (4 tools)
   - `get_quotes()` - Real-time quotes via DXLink
   - `get_greeks()` - Option Greeks via DXLink
   - `get_market_metrics()` - IV rank, liquidity, earnings
   - `market_status()` - Exchange hours and holidays

3. **History** (2 tools)
   - `get_transaction_history()` - Trades, deposits, withdrawals
   - `get_order_history()` - Past orders

4. **Trading** (4 tools)
   - `get_live_orders()` - Active orders
   - `place_order()` - Multi-leg order placement
   - `replace_order()` - Modify existing orders
   - `delete_order()` - Cancel orders

5. **Watchlists** (3 tools)
   - `get_watchlists()` - List watchlists
   - `manage_private_watchlist()` - Add/remove symbols
   - `delete_private_watchlist()` - Delete watchlist

6. **Search** (1 tool)
   - `search_symbols()` - Symbol lookup

7. **Utility** (1 tool)
   - `get_current_time_nyc()` - Market time

8. **Analysis** (1 prompt)
   - `analyze_iv_opportunities` - IV rank analysis prompt

#### Supporting Infrastructure

**Rate Limiter**
```python
rate_limiter = AsyncLimiter(5, 1)  # 5 requests per second
```
- Prevents API throttling
- Applied to all API calls

**Option Chain Cache**
```python
@cached(ttl=86400, cache=Cache.MEMORY)  # 24 hour TTL
async def a_get_option_chain(...)
```
- Reduces redundant API calls
- Per-symbol caching

**Instrument Resolution**
```python
async def get_instrument_details(session, instruments):
    # Validates option parameters
    # Returns streamer symbols
    # Caches results
```

**Logging Configuration**
```python
# Applied AFTER imports to override tastytrade defaults
logging.getLogger('tastytrade').setLevel(logging.CRITICAL)
logging.getLogger('websockets').setLevel(logging.CRITICAL)
```

### 3. TastyTrade API Layer

**tastytrade SDK (v11.0.0)**
- Official Python SDK
- Provides typed Pydantic models
- Handles OAuth2 authentication
- Both sync and async methods

**Session Class**
- OAuth2 token management
- 15-minute session token TTL
- Never-expiring refresh token
- Manual refresh required (no auto-refresh)

**DXLinkStreamer**
- WebSocket connection for real-time data
- Used by `get_quotes()` and `get_greeks()`
- Handles out-of-order message arrivals

**REST API**
- Base URL: `https://api.tastyworks.com`
- OAuth2 endpoints: `/oauth/token`
- Account APIs: `/accounts/{account_number}/...`
- Market data: `/market-metrics`, `/symbols/search`

## Data Flow Examples

### Example 1: Get Account Balances

```
User: "Show my account balances"
  ↓
Agent (LLM): Decides to call get_balances tool
  ↓
MCP Server: get_balances(ctx)
  ↓
Session Check: ensure_session_valid(session)
  ├─ If expired → await session.a_refresh()
  └─ Else → continue
  ↓
Rate Limiter: async with rate_limiter
  ↓
TastyTrade SDK: await account.a_get_balances(session)
  ↓
HTTP Request: GET /accounts/{id}/balances
  ↓
TastyTrade API: Returns account balance JSON
  ↓
Pydantic Model: AccountBalance parsed
  ↓
Filter: Remove null/zero values
  ↓
MCP Server: Returns dict to agent
  ↓
Agent (LLM): Formats response for user
  ↓
User: Sees formatted balance information
```

### Example 2: Place Multi-Leg Order

```
User: "Buy a call spread on SPY"
  ↓
Agent (LLM): Decides parameters and calls place_order
  ↓
MCP Server: place_order(ctx, legs=[...], price=None)
  ↓
Session Check: ensure_session_valid(session)
  ↓
Instrument Resolution: get_instrument_details(session, legs)
  ├─ Validate strike, expiration, type
  ├─ Get option chain (cached 24hr)
  └─ Return streamer symbols
  ↓
Auto-Pricing (if price=None): calculate_net_price(ctx, instruments, legs)
  ├─ Open DXLink WebSocket
  ├─ Subscribe to quotes
  ├─ Collect bid/ask for each leg
  ├─ Calculate net mid-price
  └─ Close WebSocket
  ↓
Rate Limiter: async with rate_limiter
  ↓
Order Creation: NewOrder(legs=[...], price=...)
  ↓
TastyTrade SDK: await account.a_place_order(session, order)
  ↓
HTTP Request: POST /accounts/{id}/orders
  ↓
TastyTrade API: Creates order, returns order object
  ↓
MCP Server: Returns order details
  ↓
Agent (LLM): Confirms order placement to user
  ↓
User: Sees order confirmation
```

### Example 3: Token Refresh Flow

```
Time: T+14min (1 minute before expiration)
  ↓
User: "What's the IV rank for AAPL?"
  ↓
MCP Server: get_market_metrics(ctx, ["AAPL"])
  ↓
Session Check: ensure_session_valid(session)
  ├─ current_time = now_in_new_york()
  ├─ Check: current_time >= session_expiration - 1min
  ├─ ✓ True: Token expires soon
  └─ Call: await session.a_refresh()
      ↓
      HTTP Request: POST /oauth/token
      {
        "grant_type": "refresh_token",
        "client_secret": "...",
        "refresh_token": "..."
      }
      ↓
      TastyTrade API: Returns new access token
      ↓
      Session Updated:
        • session_token = new token
        • session_expiration = now + 15min
        • httpx clients updated with new token
      ↓
      Log: "🔄 Token refreshed"
  ↓
Continue with original request...
  ↓
User: Sees IV rank (doesn't notice refresh happened)
```

## Configuration Flow

```
.env File
  ↓
  ├─ TASTYTRADE_CLIENT_SECRET ────────┐
  ├─ TASTYTRADE_REFRESH_TOKEN ────────┤
  ├─ TASTYTRADE_ACCOUNT_ID ───────────┤
  ├─ MODEL_IDENTIFIER ────────────────┤
  ├─ OPENAI_API_KEY ──────────────────┤
  ├─ LOG_LEVEL ───────────────────────┤
  └─ AGENT_CUSTOM_RULES ──────────────┤
                                       ↓
                              load_dotenv()
                                       ↓
                  ┌────────────────────┴─────────────────────┐
                  │                                            │
            agent.py                                     server.py
                  │                                            │
    ┌─────────────┼────────────┐                ┌────────────┼──────────┐
    │             │            │                │            │          │
  Model      System Prompt  OpenAI        Session       Logging    Account
  Config     + Custom Rules  Client        Creation      Config     Selection
    │             │            │                │            │          │
    ↓             ↓            ↓                ↓            ↓          ↓
pydantic-ai   SYSTEM_PROMPT  AsyncOpenAI   OAuthSession  Suppressors  Account
   Agent      .format()       (optional)    (client_secret, (tastytrade, object
                                            refresh_token)   websockets)
```

## Security & Best Practices

### 1. Credential Management
```
✓ .env file (gitignored)
✓ Environment variables
✓ Never commit secrets
✗ DO NOT hardcode credentials
```

### 2. Token Security
```
• Session tokens: 15 min lifetime
• Refresh tokens: Never expire (keep secure!)
• Automatic refresh: 1 min before expiry
• Tokens in memory only (not persisted)
```

### 3. Rate Limiting
```
• 5 requests/second (configurable)
• Prevents API throttling
• Applied consistently across all calls
```

### 4. Error Handling
```
• Comprehensive try/catch blocks
• Graceful degradation
• User-friendly error messages
• Detailed logging for debugging
```

### 5. Logging Hygiene
```
• Suppress noisy third-party logs
• INFO level for important events
• DEBUG for troubleshooting
• Never log sensitive data (tokens, passwords)
```

## Performance Optimizations

### 1. Caching Strategy
```
Option Chains:    24 hour TTL (rarely change)
Market Data:      Real-time (no cache)
Instrument Info:  Per-request (validate params)
```

### 2. Concurrent Operations
```
• Async/await throughout
• Parallel tool calls supported
• Non-blocking I/O
• WebSocket for real-time data
```

### 3. Connection Pooling
```
• httpx clients (sync + async)
• Reused across requests
• Automatic keep-alive
• Connection limits enforced
```

## Deployment Options

### Option 1: Local CLI (Development)
```bash
uv run chat.py
```
- Best for: Testing, personal use
- Transport: stdio subprocess
- Pros: Simple, secure (local only)
- Cons: Single user, no remote access

### Option 2: Claude Desktop (Production)
```json
{
  "mcpServers": {
    "tastytrade": {
      "command": "uvx",
      "args": ["tasty-agent"],
      "env": { "TASTYTRADE_CLIENT_SECRET": "..." }
    }
  }
}
```
- Best for: Personal AI assistant
- Transport: stdio
- Pros: GUI, persistent, integrated
- Cons: Desktop only

### Option 3: HTTP Server (Multi-user)
```bash
tasty-agent-http --host 0.0.0.0 --port 8000
```
- Best for: Team use, remote agents
- Transport: HTTP/SSE
- Pros: Multiple clients, remote access
- Cons: Security concerns, needs auth

### Option 4: Background Bot (Automation)
```bash
uv run background.py "Monitor portfolio" --hourly
```
- Best for: Automated trading, alerts
- Transport: stdio subprocess
- Pros: Scheduled, autonomous
- Cons: Runs independently

## Future Enhancements

### Potential Additions
1. **Persistent Storage**: SQLite for conversation history
2. **User Preferences**: Per-account trading rules
3. **Trade Journals**: Automatic trade logging
4. **Performance Analytics**: P&L tracking, win rates
5. **Real-time Alerts**: Price/volatility notifications
6. **Multi-account**: Support multiple TastyTrade accounts
7. **Paper Trading**: Test mode with simulated orders
8. **Backtesting**: Historical strategy testing

### Scalability Considerations
1. **Database**: PostgreSQL for multi-user
2. **Redis**: Distributed caching
3. **Queue**: Celery for background tasks
4. **Auth**: JWT tokens for HTTP mode
5. **Monitoring**: Prometheus metrics
6. **Logging**: Structured logs (JSON)
