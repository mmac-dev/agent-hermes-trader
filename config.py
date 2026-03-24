"""
config.py - Shared configuration for the trading agent.
"""

import os
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path.home() / '.hermes' / '.env'
if env_path.exists():
    load_dotenv(env_path)

TRADER_DIR = Path(__file__).parent.resolve()

# API Keys
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')

# Models
ANALYSIS_MODEL = 'qwen/qwen3.5-27b'
REVIEW_MODEL = 'minimax/minimax-m2.1'

# Trading parameters
SYMBOL = 'BTC/USDT'
MIN_RR = 2.0
MIN_CONFIDENCE = 55
MAX_OPEN_POSITIONS = 6  # Increased for multi-asset (2 per symbol × 3 symbols)
REVIEW_EVERY_N = 3
POSITION_TIMEOUT_HOURS = 48

# Paths
STRATEGY_NOTES_PATH = TRADER_DIR / 'strategy_notes.md'
TELEGRAM_NOTIFY_PATH = TRADER_DIR / '.telegram_notify'

# Per-symbol Telegram bots
TELEGRAM_BOTS = {
    'BTC/USDT': {
        'token': os.getenv('TELEGRAM_BTC_BOT_TOKEN', ''),
        'chat_id': os.getenv('TELEGRAM_BTC_CHAT_ID', ''),
    },
    'ETH/USDT': {
        'token': os.getenv('TELEGRAM_ETH_BOT_TOKEN', ''),
        'chat_id': os.getenv('TELEGRAM_ETH_CHAT_ID', ''),
    },
    'SOL/USDT': {
        'token': os.getenv('TELEGRAM_SOL_BOT_TOKEN', ''),
        'chat_id': os.getenv('TELEGRAM_SOL_CHAT_ID', ''),
    },
    'LINK/USDT': {
        'token': os.getenv('TELEGRAM_LINK_BOT_TOKEN', ''),
        'chat_id': os.getenv('TELEGRAM_LINK_CHAT_ID', ''),
    },
}


def llm_call(model: str, system: str, user: str, max_tokens: int = 1500) -> str:
    """Call OpenRouter inference with retry logic."""
    import time
    headers = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://greynode.co.uk',
        'X-Title': 'Hermes Trading Agent',
    }
    payload = {
        'model': model,
        'max_tokens': max_tokens,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user',   'content': user},
        ],
    }
    max_retries = 3
    delay_seconds = 2
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            if content and content.strip():
                return content.strip()
            print(f"[llm_call] Empty response on attempt {attempt}/{max_retries}")
        except requests.exceptions.Timeout:
            print(f"[llm_call] Timeout on attempt {attempt}/{max_retries}")
        except requests.exceptions.RequestException as e:
            print(f"[llm_call] Request error on attempt {attempt}/{max_retries}: {e}")
        except Exception as e:
            print(f"[llm_call] Unexpected error on attempt {attempt}/{max_retries}: {e}")
        if attempt < max_retries:
            print(f"[llm_call] Retrying in {delay_seconds}s...")
            time.sleep(delay_seconds)
    raise RuntimeError(f"LLM call failed after {max_retries} attempts")
