#!/usr/bin/env python3
"""Passport-platform verification entrypoint."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent_passport" / "src"))

from agent_passport.demo import build_demo_core  # noqa: E402
from agent_passport.verify import run_checks  # noqa: E402


def verify() -> list[dict[str, object]]:
    return [result.__dict__ for result in run_checks(build_demo_core())]


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
