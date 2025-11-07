# Data Storage Guide

## Current Storage

### 1. **Environment Variables** (.env)
Stores: Configuration, API keys, custom rules
- ✅ Simple, no database needed
- ✅ Version-controllable (via .env.example)
- ❌ Not suitable for conversation history

### 2. **In-Memory Cache** (aiocache)
Stores: Option chains (24hr TTL)
- Location: `tasty_agent/server.py:171`
- Purpose: Reduce API calls
- ❌ Lost on restart

### 3. **Message History** (Pydantic-AI)
Stores: Conversation context
- Location: In-memory during chat session
- Usage: `result.new_messages()` in chat.py:30
- ❌ Lost when chat ends

## Adding Persistent Storage

### Option 1: **SQLite** (Recommended for Local Use)

Simple local database for storing conversation history, user preferences, trade logs.

```bash
# Install
uv add sqlalchemy aiosqlite

# Create tasty_agent/database.py
```

```python
from sqlalchemy import create_engine, Column, String, DateTime, JSON
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()

class ConversationHistory(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    messages = Column(JSON)  # Store chat history
    account_id = Column(String)

class UserPreferences(Base):
    __tablename__ = "preferences"

    account_id = Column(String, primary_key=True)
    custom_rules = Column(String)
    risk_tolerance = Column(String)
    default_position_size = Column(JSON)

# Initialize
engine = create_async_engine("sqlite+aiosqlite:///data/tasty-agent.db")
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

### Option 2: **JSON Files** (Simplest)

Good for user preferences and trade logs.

```python
# tasty_agent/storage.py
import json
from pathlib import Path

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

def save_preferences(account_id: str, preferences: dict):
    """Save user preferences to JSON."""
    file_path = DATA_DIR / f"{account_id}_preferences.json"
    with open(file_path, "w") as f:
        json.dump(preferences, f, indent=2)

def load_preferences(account_id: str) -> dict:
    """Load user preferences from JSON."""
    file_path = DATA_DIR / f"{account_id}_preferences.json"
    if file_path.exists():
        with open(file_path, "r") as f:
            return json.load(f)
    return {}
```

### Option 3: **Redis** (For Production/Multi-User)

Fast cache + persistent storage for conversation history.

```bash
# Install
uv add redis[hiredis]

# Start Redis
docker run -d -p 6379:6379 redis:alpine
```

```python
import redis.asyncio as redis
from datetime import timedelta

# Connect
r = await redis.Redis(host='localhost', port=6379, decode_responses=True)

# Store conversation
await r.setex(
    f"chat:{session_id}",
    timedelta(hours=24),
    json.dumps(messages)
)

# Retrieve
messages = json.loads(await r.get(f"chat:{session_id}"))
```

### Option 4: **PostgreSQL/MySQL** (Enterprise)

Full-featured database for multi-user, audit logs, analytics.

## Example: Add Conversation Persistence

```python
# In agent.py, add:
from dataclasses import dataclass
from typing import List

@dataclass
class ConversationStore:
    """Simple file-based conversation storage."""

    def save(self, session_id: str, messages: List[dict]):
        path = Path(f"data/conversations/{session_id}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(messages, f, indent=2)

    def load(self, session_id: str) -> List[dict]:
        path = Path(f"data/conversations/{session_id}.json")
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
        return []

# In chat.py, use it:
store = ConversationStore()
session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

# Load previous messages
previous = store.load(session_id)

# Run agent with history
result = await agent.run(user_input, message_history=previous)

# Save after each exchange
store.save(session_id, result.all_messages())
```

## Recommendation

**For your use case (personal trading assistant):**

1. **Start with JSON files** for user preferences
2. **Use SQLite** if you want conversation history
3. **Keep using .env** for rules and config

**Example structure:**
```
data/
  ├── preferences.json         # User settings
  ├── trade_log.json           # Manual trade records
  └── conversations/           # Chat history
      ├── 20250104_093000.json
      └── 20250104_143000.json
```

## Quick Start: Add JSON Storage

Add to your `.env`:
```bash
# Data storage location
DATA_DIR=./data
```

That's it! Simple, no database required. 🎯
