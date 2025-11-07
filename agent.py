import logging
import os

from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPServerStdio

logger = logging.getLogger(__name__)
load_dotenv()

# System prompt - rules that apply to EVERY interaction
SYSTEM_PROMPT = """You are a helpful TastyTrade trading assistant.

**Core Rules:**
- Always confirm before executing real trades (dry_run=False)
- Provide risk warnings for complex options strategies
- Show portfolio impact before large trades
- Use concise, clear language
- When showing quotes or positions, format data in readable tables

**Trading Guidelines:**
- For options: Always check IV rank before suggesting trades
- Monitor portfolio Greeks (delta, theta exposure)
- Suggest position sizing based on account balance
- Warn about earnings dates and high-volatility events

**Custom Rules (loaded from env):**
{custom_rules}
"""

def create_tastytrader_agent() -> Agent:
    """Create and return a configured agent instance."""

    model_identifier = os.getenv('MODEL_IDENTIFIER', 'openai:gpt-4o-mini')
    openai_base_url = os.getenv('OPENAI_BASE_URL')  # Optional: for OpenAI-compatible APIs
    custom_rules = os.getenv('AGENT_CUSTOM_RULES', 'None specified')  # Load custom rules from .env

    logger.info(f"Creating agent with model: {model_identifier}")
    if openai_base_url:
        logger.info(f"Using custom OpenAI base URL: {openai_base_url}")

    try:
        # Set up environment for MCP server subprocess
        server_env = dict(os.environ)
        # Suppress MCP server logs by setting PYTHONWARNINGS to ignore
        server_env['PYTHONWARNINGS'] = 'ignore'

        server = MCPServerStdio(
            'uv', args=['run', 'tasty-agent', 'stdio'], timeout=60, env=server_env
        )

        # Format system prompt with custom rules
        system_prompt = SYSTEM_PROMPT.format(custom_rules=custom_rules)

        # Create agent with system prompt
        if openai_base_url and model_identifier.startswith('openai:'):
            from openai import AsyncOpenAI
            openai_client = AsyncOpenAI(base_url=openai_base_url)
            agent = Agent(
                model_identifier,
                toolsets=[server],
                openai_client=openai_client,
                system_prompt=system_prompt
            )
        else:
            agent = Agent(
                model_identifier,
                toolsets=[server],
                system_prompt=system_prompt
            )

        logger.info("TastyTrader agent created successfully")
        return agent
    except Exception as e:
        logger.error(f"Failed to create TastyTrader agent: {e}")
        raise