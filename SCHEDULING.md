# Background Scheduling Guide

## Overview

The `background.py` script runs the TastyTrade agent autonomously on a schedule or period. Perfect for monitoring portfolios, executing strategies, or getting alerts.

## How It Works

### Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│  1. Parse CLI Arguments                                  │
│     --hourly / --daily / --period / --schedule          │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│  2. Calculate Schedule Time (if specified)               │
│     - Parse time string (9:30am → datetime)             │
│     - Convert to NYC timezone                            │
│     - If time passed today, schedule for tomorrow        │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│  3. Wait Until Schedule Time (if specified)              │
│     asyncio.sleep(seconds_until_schedule)                │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│  4. Create Pydantic-AI Agent                             │
│     agent = create_tastytrader_agent()                   │
│     - Spawns MCP server subprocess                       │
│     - Connects to LLM (OpenAI/Claude/etc)                │
└────────────────┬────────────────────────────────────────┘
                 │
                 ├─ If periodic ─────────┐
                 │                       │
                 │              ┌────────▼─────────────────┐
                 │              │  5a. Periodic Loop       │
                 │              │  while True:             │
                 │              │    • Check market hours  │
                 │              │    • Run agent           │
                 │              │    • Sleep for period    │
                 │              └──────────────────────────┘
                 │
                 └─ If one-time ────────┐
                                        │
                                ┌───────▼──────────────────┐
                                │  5b. Single Execution     │
                                │  • Check market hours     │
                                │  • Run agent once         │
                                │  • Exit                   │
                                └───────────────────────────┘
```

## Scheduling Options

### 1. One-Time Execution

Run once, then exit:

```bash
uv run background.py "Check my portfolio and send me a summary"
```

**Output:**
```
2025-11-19 10:30:00 - INFO - Running agent...
🤖 Your portfolio is currently valued at $125,430.50...
```

### 2. Periodic Execution (--hourly)

**How --hourly Works:**

```python
# Line 80: --hourly flag
hourly: bool = typer.Option(False, "--hourly", help="Run every hour")

# Line 116: Converts to period in seconds
final_period = 3600 if hourly else ...  # 3600 seconds = 1 hour

# Lines 50-60: Periodic loop
if period:
    while True:
        if market_open_only and not check_market_open():
            logger.info("Markets are closed, skipping agent run.")
        else:
            logger.info("Running agent...")
            result = await agent.run(instructions)
        await asyncio.sleep(period)  # Sleep for 3600 seconds (1 hour)
```

**Example:**

```bash
uv run background.py "Monitor my positions" --hourly
```

**Timeline:**
```
10:00:00 - First run: "Monitor my positions"
           Sleep 3600 seconds (1 hour)
11:00:00 - Second run: "Monitor my positions"
           Sleep 3600 seconds
12:00:00 - Third run: "Monitor my positions"
           ...continues forever until Ctrl+C
```

### 3. Periodic Execution (--daily)

Same as --hourly but runs every 24 hours:

```bash
uv run background.py "Generate daily summary" --daily
```

**Timeline:**
```
10:00:00 Nov 19 - First run
           Sleep 86400 seconds (24 hours)
10:00:00 Nov 20 - Second run
           Sleep 86400 seconds
10:00:00 Nov 21 - Third run
           ...continues forever
```

### 4. Custom Period (--period)

Run at custom intervals:

```bash
# Every 30 minutes
uv run background.py "Check volatility" --period 1800

# Every 5 minutes
uv run background.py "Monitor alerts" --period 300

# Every 2 hours
uv run background.py "Rebalance check" --period 7200
```

### 5. Scheduled Time (--schedule)

Run at a specific time, then exit:

```bash
uv run background.py "Execute morning strategy" --schedule "9:30am"
```

**How It Works:**

```python
# Lines 94-113: Parse schedule time
if schedule_str:
    nyc_tz = ZoneInfo('America/New_York')
    parsed_time = datetime.strptime(schedule_str, '%I:%M%p').time()
    nyc_now = datetime.now(nyc_tz)
    schedule_time = datetime.combine(nyc_now.date(), parsed_time, nyc_tz)

    # If time has passed today, schedule for tomorrow
    if schedule_time <= nyc_now:
        schedule_time += timedelta(days=1)

# Lines 43-46: Wait until schedule time
if schedule:
    sleep_seconds = (schedule - datetime.now()).total_seconds()
    if sleep_seconds > 0:
        await asyncio.sleep(sleep_seconds)
```

**Timeline:**
```
Current time: 8:00am
Command: background.py "Execute strategy" --schedule "9:30am"

8:00am - Script starts
         Calculates: 9:30am - 8:00am = 5400 seconds
         asyncio.sleep(5400)
9:30am - Wakes up
         Runs agent with "Execute strategy"
         Exits
```

**If time already passed:**
```
Current time: 10:00am
Command: background.py "Execute strategy" --schedule "9:30am"

10:00am - Script starts
          Detects 9:30am has passed today
          Schedules for tomorrow 9:30am
          Sleep until then (23.5 hours)
9:30am (next day) - Wakes up, runs agent, exits
```

### 6. Combined: Schedule + Periodic

Run at specific time, then repeat on interval:

```bash
# Run at 9:30am, then every hour after
uv run background.py "Trading bot" --schedule "9:30am" --hourly
```

**Timeline:**
```
8:00am - Script starts, waits until 9:30am
9:30am - First run
         Sleep 3600 seconds
10:30am - Second run
          Sleep 3600 seconds
11:30am - Third run
          ...continues every hour
```

```bash
# Run at market open, then every 30 minutes
uv run background.py "Monitor dips" --market-open --period 1800
```

### 7. Market Hours Awareness

By default, the bot checks if markets are open before running:

```bash
# Only runs when NYSE is open
uv run background.py "Trade executor" --hourly
```

**Market Check Logic:**

```python
# Lines 33-40: Check if market is open
def check_market_open() -> bool:
    session = create_tastytrade_session()
    market_sessions = asyncio.run(a_get_market_sessions(session, [ExchangeType.NYSE]))
    return any(market_session.status == MarketStatus.OPEN for market_session in market_sessions)

# Lines 54-55: Skip if market closed
if market_open_only and not check_market_open():
    logger.info("Markets are closed, skipping agent run.")
```

**Timeline with --hourly:**
```
8:00am - Markets closed, skips
9:00am - Markets closed, skips
9:30am - Markets open, runs! ✅
10:30am - Markets open, runs! ✅
11:30am - Markets open, runs! ✅
...
4:00pm - Markets closed, skips
5:00pm - Markets closed, skips
```

**Override market check:**

```bash
# Run even when markets are closed
uv run background.py "Portfolio check" --hourly --ignore-market-hours
```

## Practical Examples

### Example 1: Morning Alert

Get notified every morning at 8am about overnight changes:

```bash
uv run background.py "Check my positions and alert me of any significant changes" --schedule "8:00am" --daily
```

### Example 2: Intraday Monitoring

Monitor specific stocks during market hours:

```bash
uv run background.py "Check AAPL and TSLA for entry opportunities" --market-open --period 1800
```

**What happens:**
- Waits until 9:30am EST
- Runs at 9:30am, then every 30 minutes
- Stops running after 4:00pm (market close)
- Resumes next day at 9:30am

### Example 3: End-of-Day Summary

Generate daily report at market close:

```bash
uv run background.py "Generate today's trading summary with P&L" --schedule "4:00pm" --daily
```

### Example 4: Volatility Monitor

Check IV rank every hour, all day:

```bash
uv run background.py "Alert me if any watchlist symbols have IV rank > 80" --hourly --ignore-market-hours
```

### Example 5: Rebalancing Bot

Check portfolio balance every 2 hours during market:

```bash
uv run background.py "Rebalance portfolio if any position exceeds 20%" --market-open --period 7200
```

## Running in Background

### Using nohup (Unix/Mac)

```bash
# Run in background, survives terminal close
nohup uv run background.py "Monitor portfolio" --hourly > bot.log 2>&1 &

# View logs
tail -f bot.log

# Stop the bot
ps aux | grep background.py
kill <pid>
```

### Using screen (Unix/Mac)

```bash
# Start a screen session
screen -S trading-bot

# Run the bot
uv run background.py "Trading strategy" --hourly

# Detach: Ctrl+A, then D

# Reattach later
screen -r trading-bot

# Stop: Ctrl+C inside screen
```

### Using tmux (Unix/Mac)

```bash
# Start tmux
tmux new -s trading-bot

# Run the bot
uv run background.py "Monitor alerts" --period 300

# Detach: Ctrl+B, then D

# Reattach
tmux attach -t trading-bot
```

### Using systemd (Linux)

Create `/etc/systemd/system/tasty-bot.service`:

```ini
[Unit]
Description=TastyTrade Trading Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/tasty-agent-1
Environment=TASTYTRADE_CLIENT_SECRET=your_secret
Environment=TASTYTRADE_REFRESH_TOKEN=your_token
ExecStart=/usr/local/bin/uv run background.py "Trading strategy" --hourly
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable tasty-bot
sudo systemctl start tasty-bot
sudo systemctl status tasty-bot
sudo journalctl -u tasty-bot -f  # View logs
```

## Environment Variables

The bot needs these environment variables:

```bash
export TASTYTRADE_CLIENT_SECRET="your_secret"
export TASTYTRADE_REFRESH_TOKEN="your_token"
export TASTYTRADE_ACCOUNT_ID="your_account"  # Optional
export MODEL_IDENTIFIER="openai:gpt-4o-mini"  # Optional
export OPENAI_API_KEY="your_key"
```

Or use a `.env` file (loaded automatically).

## Logging

The bot logs to stdout with this format:

```
2025-11-19 10:30:00 - INFO - Running agent...
2025-11-19 10:30:05 - INFO - Markets are open
🤖 [Agent output here]
2025-11-19 10:30:10 - INFO - Sleeping for 3600 seconds
```

Redirect to file:

```bash
uv run background.py "instructions" --hourly > bot.log 2>&1
```

## Error Handling

### Market Check Failures

If market status check fails, the bot proceeds anyway:

```python
except Exception as e:
    logger.warning(f"Failed to check market status: {e}. Proceeding with agent run.")
    return True  # Proceed with run
```

### Agent Failures

If the agent fails, the exception propagates and the script exits. Use systemd or supervisor to auto-restart.

### Keyboard Interrupt

Press Ctrl+C to gracefully stop:

```python
try:
    while True:
        # Run agent
        await asyncio.sleep(period)
except KeyboardInterrupt:
    pass  # Clean exit
```

## Advanced Usage

### Conditional Execution in Instructions

The agent can make decisions based on market conditions:

```bash
uv run background.py "
If VIX is above 25:
  - Check my portfolio Greeks
  - Alert me if total delta exceeds 100
  - Suggest hedges if needed
Else:
  - Just monitor positions
" --hourly
```

### Chaining Multiple Bots

Run multiple bots for different strategies:

```bash
# Terminal 1: Volatility monitor
uv run background.py "Monitor IV rank for watchlist" --period 1800

# Terminal 2: Portfolio rebalancer
uv run background.py "Rebalance if needed" --hourly

# Terminal 3: Earnings alerts
uv run background.py "Alert on upcoming earnings" --daily
```

## Troubleshooting

### Bot Doesn't Run at Scheduled Time

Check timezone - all times are NYC (America/New_York):

```bash
# Verify current NYC time
TZ=America/New_York date

# Use 12-hour format with am/pm
--schedule "9:30am"  # ✅ Correct
--schedule "9:30"    # ❌ Wrong (24-hour not supported)
```

### Bot Skips Runs

Market hours check may be blocking:

```bash
# Check if markets are open
uv run python -c "from background import check_market_open; print(check_market_open())"

# Override with --ignore-market-hours
uv run background.py "instructions" --hourly --ignore-market-hours
```

### Agent Times Out

Increase timeout in agent.py if needed:

```python
server = MCPServerStdio(
    'uv', args=['run', 'tasty-agent', 'stdio'], timeout=120  # Increase from 60
)
```

## Performance Considerations

### Token Refresh

The bot automatically refreshes TastyTrade tokens every 14 minutes. No manual intervention needed.

### LLM Costs

Running hourly with GPT-4o-mini:
- ~500 tokens per run
- ~$0.001 per run
- ~$0.024 per day
- ~$0.72 per month

Use cheaper models for frequent checks:

```bash
MODEL_IDENTIFIER=groq:llama-3.1-70b-versatile uv run background.py "..." --hourly
```

### Rate Limiting

The MCP server has built-in rate limiting (5 req/sec). The bot respects this automatically.

## Best Practices

1. **Start with dry runs**: Test instructions manually first
2. **Use --ignore-market-hours for testing**: Don't wait for market open
3. **Monitor logs**: Check bot.log regularly for issues
4. **Use conservative periods**: Start with --hourly, not --period 60
5. **Set up alerts**: Have the agent notify you of important events
6. **Use systemd/supervisor for production**: Auto-restart on failures
7. **Backup credentials**: Keep .env file backed up securely
8. **Test schedule logic**: Verify times work as expected before production

## Security Notes

- **Never commit credentials**: Use .env or environment variables
- **Restrict bot permissions**: Use read-only scopes if possible
- **Monitor bot activity**: Review trading history regularly
- **Use dry-run for testing**: Test strategies before live execution
- **Secure the server**: If running on a server, use firewall rules

## Summary: Scheduling Options

| Command | Behavior | Use Case |
|---------|----------|----------|
| `background.py "text"` | Run once, exit | Manual execution |
| `--hourly` | Run every hour | Frequent monitoring |
| `--daily` | Run every 24 hours | Daily summaries |
| `--period 1800` | Run every 30 min | Custom intervals |
| `--schedule "9:30am"` | Run at 9:30am once | One-time scheduled |
| `--market-open` | Run at 9:30am once | Market open execution |
| `--schedule "9:30am" --hourly` | Run at 9:30am, then hourly | Scheduled + periodic |
| `--ignore-market-hours` | Run even when closed | Testing, after-hours |
