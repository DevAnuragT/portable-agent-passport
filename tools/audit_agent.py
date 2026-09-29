#!/usr/bin/env python3
"""Audit an OpenGAP-style agent repository and emit JSON evidence."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent_passport" / "src"))

from agent_passport.audit import audit_agent  # noqa: E402


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    print(json.dumps(audit_agent(target), indent=2, sort_keys=True))
