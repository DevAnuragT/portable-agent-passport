"""CrewAI-shaped adapter with no hard dependency on CrewAI."""

from typing import Any
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_passport" / "src"))

from agent_passport.adapters import PortableJsonAdapter
from agent_passport.demo import build_demo_core


class CrewAIPortableAgent:
    def __init__(self) -> None:
        self._adapter = PortableJsonAdapter(build_demo_core())

    def kickoff(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return self._adapter.execute(inputs)
