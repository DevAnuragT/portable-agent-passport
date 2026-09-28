#!/usr/bin/env python3
"""Passport-platform entrypoint for the portable agent."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent_passport" / "src"))

from agent_passport.adapters import NativeRuntimeAdapter, PortableJsonAdapter  # noqa: E402
from agent_passport.demo import build_demo_core  # noqa: E402


def run(payload: dict[str, object]) -> dict[str, object]:
    runtime = str(payload.get("runtime", "portable-json"))
    adapter = NativeRuntimeAdapter(build_demo_core()) if runtime == "native" else PortableJsonAdapter(build_demo_core())
    return adapter.execute(payload)


if __name__ == "__main__":
    request = json.load(sys.stdin)
    print(json.dumps(run(request), sort_keys=True))
