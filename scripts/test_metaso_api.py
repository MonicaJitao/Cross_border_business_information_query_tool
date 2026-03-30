"""
Standalone probe for Metaso search API — prints structure for parser work.
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


def describe_keys(obj, indent: str = "") -> list[str]:
    lines: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            lines.append(f"{indent}{k!r}: {type(v).__name__}")
            lines.extend(describe_keys(v, indent + "  "))
    elif isinstance(obj, list):
        lines.append(f"{indent}[list len={len(obj)}]")
        if obj:
            lines.extend(describe_keys(obj[0], indent + "  "))
    return lines


def first_list_of_dicts(obj):
    """First list in depth-first order whose items are all dicts (may be empty)."""
    if isinstance(obj, list):
        if all(isinstance(x, dict) for x in obj):
            return obj
        for x in obj:
            found = first_list_of_dicts(x)
            if found is not None:
                return found
    elif isinstance(obj, dict):
        for v in obj.values():
            found = first_list_of_dicts(v)
            if found is not None:
                return found
    return None


def main() -> int:
    print("=" * 60)
    print("Metaso API probe")
    print("=" * 60)

    load_env()
    key = os.environ.get("METASO_API_KEY", "").strip()
    if not key:
        print("ERROR: METASO_API_KEY missing in environment / .env", file=sys.stderr)
        return 1

    url = "https://metaso.cn/api/v1/search"
    body = {
        "q": "华为技术有限公司 进出口 跨境贸易",
        "scope": "webpage",
        "includeSummary": True,
        "size": 5,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        with httpx.Client(timeout=60.0, trust_env=False) as client:
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

    text = r.text
    if r.status_code >= 400:
        print("\n--- Error response (raw) ---")
        print(text)

    try:
        data = r.json()
    except json.JSONDecodeError:
        print("\n--- Body (not JSON) ---")
        print(text[:2000])
        return 0

    print("\n--- JSON key tree (types) ---")
    for line in describe_keys(data):
        print(line)

    print("\n--- First 2 result items (detail) ---")
    lst = first_list_of_dicts(data)
    if lst is None:
        print("(No list of dicts found; showing raw JSON preview)")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])
    else:
        for i, item in enumerate(lst[:2]):
            print(f"\n--- item[{i}] ---")
            print(json.dumps(item, ensure_ascii=False, indent=2))
        if len(lst) == 0:
            print("(List is empty)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
