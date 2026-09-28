"""Claude-Code-shaped adapter with no hard dependency on Claude Code."""

from typing import Any
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_passport" / "src"))

from agent_passport.adapters import PortableJsonAdapter
from agent_passport.demo import build_demo_core


def run(task: str, **_: Any) -> dict[str, Any]:
    return PortableJsonAdapter(build_demo_core()).execute({"task": task})
