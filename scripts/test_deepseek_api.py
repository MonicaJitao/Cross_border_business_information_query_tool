"""
Standalone probe for DeepSeek chat completions (OpenAI-compatible).
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


def main() -> int:
    print("=" * 60)
    print("DeepSeek API probe")
    print("=" * 60)

    load_env()
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    model = os.environ.get("DEEPSEEK_DEFAULT_MODEL", "deepseek-chat").strip() or "deepseek-chat"

    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY missing in environment / .env", file=sys.stderr)
        return 1

    url = f"{base}/chat/completions"
    body = {
        "model": model,
        "messages": [
            {"role": "user", "content": "你好，请用一句话介绍自己"},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
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

    print("\n--- Model ---")
    print(data.get("model", "(missing)"))

    print("\n--- Usage ---")
    usage = data.get("usage")
    if usage is None:
        print("(missing)")
    else:
        print(json.dumps(usage, ensure_ascii=False, indent=2))

    content = ""
    try:
        choices = data.get("choices") or []
        if choices:
            msg = choices[0].get("message") or {}
            content = msg.get("content") or ""
    except (TypeError, AttributeError):
        content = ""

    print("\n--- Content (first 200 chars) ---")
    preview = (content or "")[:200]
    print(repr(preview))

    if r.status_code >= 400:
        print("\n--- Error payload ---")
        print(json.dumps(data, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
