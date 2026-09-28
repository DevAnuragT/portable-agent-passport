"""Deterministic demo provider and sample passport construction."""

from __future__ import annotations

from .core import AgentCore, ModelProvider
from .manifest import PassportManifest


class DemoModel(ModelProvider):
    """Offline provider used for reproducible tests and demonstrations."""

    def generate(self, prompt: str) -> str:
        task = prompt.rsplit("\n", 1)[-1].strip()
        return f"Demo answer: {task}"


def build_demo_core() -> AgentCore:
    manifest = PassportManifest(
        name="portable-research-agent",
        version="0.1.0",
        capabilities=("answer", "summarise"),
        input_schema={"type": "object", "required": ["task"]},
        output_schema={"type": "object", "required": ["answer", "trace"]},
        runtimes=("native", "portable-json"),
    )
    return AgentCore(manifest, DemoModel())
