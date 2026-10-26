#!/usr/bin/env python3
"""Simple client for Astro KB FastAPI /api/answer endpoint.

Usage example:
  python integration/python_api_client.py --question "Comment conjuguer avoir?" --grade 3 --language fr --subject francais --age 8
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def build_payload(
    question: str,
    grade: int | None,
    language: str,
    subject: str | None,
    age: int | None,
    conversation: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    return {
        "question": question,
        "grade": grade,
        "language": language,
        "subject": subject,
        "age": age,
        "conversation": conversation or [],
    }


def ask_api(base_url: str, payload: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/answer"
    data = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )

    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from API: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot reach API at {url}: {exc.reason}") from exc


def print_result(result: Dict[str, Any]) -> None:
    print("=" * 80)
    print("API RESPONSE")
    print("=" * 80)
    print(f"Mode: {result.get('mode')}")
    print(f"Retrieval mode: {result.get('retrieval_mode')}")
    print()
    print("Answer:")
    print(result.get("answer", ""))
    print()

    sources = result.get("sources") or []
    print(f"Sources count: {len(sources)}")
    for idx, src in enumerate(sources[:5], start=1):
        print(
            f"  [{idx}] {src.get('source_file')} | grade={src.get('grade')} "
            f"| subject={src.get('subject')} | score={src.get('score')}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Astro KB API client")
    parser.add_argument("--base-url", default=os.getenv("ASTRO_API_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--question", required=True)
    parser.add_argument("--grade", type=int, default=None)
    parser.add_argument("--language", default="auto")
    parser.add_argument("--subject", default=None)
    parser.add_argument("--age", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=60)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        question=args.question,
        grade=args.grade,
        language=args.language,
        subject=args.subject,
        age=args.age,
    )

    try:
        result = ask_api(args.base_url, payload, timeout=args.timeout)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
