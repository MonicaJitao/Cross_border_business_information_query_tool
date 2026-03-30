"""
Standalone probe for Claude proxy (Anthropic Messages API shape).
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"


def load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ENV_PATH)
    except ImportError:
        _load_env_manual(ENV_PATH)


def _load_env_manual(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def extract_text_content(data: dict) -> str:
    parts: list[str] = []
    for block in data.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            t = block.get("text")
            if isinstance(t, str):
                parts.append(t)
        elif isinstance(block, str):
            parts.append(block)
    return "".join(parts)


def main() -> int:
    print("=" * 60)
    print("Claude proxy (Messages API) probe")
    print("=" * 60)

    load_env()
    api_key = os.environ.get("CLAUDE_PROXY_API_KEY", "").strip()
    base = os.environ.get("CLAUDE_PROXY_BASE_URL", "https://gaccode.com/claudecode").rstrip("/")
    model = os.environ.get("CLAUDE_PROXY_DEFAULT_MODEL", "claude-sonnet-4-6").strip() or "claude-sonnet-4-6"

    if not api_key:
        print("ERROR: CLAUDE_PROXY_API_KEY missing in environment / .env", file=sys.stderr)
        return 1

    url = f"{base}/v1/messages"
    body = {
        "model": model,
        "max_tokens": 256,
        "messages": [
            {"role": "user", "content": "你好，请用一句话介绍自己"},
        ],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=120.0, trust_env=False) as client:
            r = client.post(url, json=body, headers=headers)
    except httpx.HTTPError as e:
        print("REQUEST FAILED:", repr(e), file=sys.stderr)
        traceback.print_exc()
        return 1
    except Exception as e:
        print("UNEXPECTED ERROR:", repr(e), file=sys.stderr)
        traceback.print_exc()
        return 1

    print("\n--- HTTP status ---")
    print(r.status_code)

    if r.status_code >= 400:
        print("\n--- Error response (raw) ---")
        print(r.text)

    try:
        data = r.json()
    except json.JSONDecodeError:
        print("\n--- Body (not JSON) ---")
        print(r.text[:2000])
        return 0

    print("\n--- Full response JSON ---")
    print(json.dumps(data, ensure_ascii=False, indent=2))

    print("\n--- Content text ---")
    if isinstance(data, dict):
        text = extract_text_content(data)
        print(text if text else "(no text blocks found)")
    else:
        print("(response is not an object)")

    if r.status_code >= 400:
        print("\n--- Note: non-success status above ---", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
