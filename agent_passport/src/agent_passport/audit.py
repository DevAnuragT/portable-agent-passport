"""Deterministic audit of an OpenGAP-style agent repository."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    message: str
    evidence: str
    fix: str


def audit_agent(path: str | Path) -> dict[str, Any]:
    """Inspect identity, explanation, skills, tools, and safety files."""
    root = Path(path).expanduser().resolve()
    findings: list[Finding] = []

    required = ("agent.yaml", "SOUL.md", "RULES.md", "DUTIES.md", "AGENTS.md", "EXPLAINABILITY.md")
    for filename in required:
        if not (root / filename).is_file():
            findings.append(Finding("required-file", "error", f"Missing {filename}", filename, f"Add {filename} at repository root."))

    manifest = root / "agent.yaml"
    if manifest.is_file():
        text = manifest.read_text(encoding="utf-8")
        name_match = re.search(r"^name:\s*([^\s]+)$", text, re.MULTILINE)
        if not name_match or not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", name_match.group(1)):
            findings.append(Finding("manifest-name", "error", "Agent name is not lowercase kebab-case", "agent.yaml:name", "Use a name beginning with a letter and containing lowercase hyphenated words."))
        for key in ("version", "description"):
            if not re.search(rf"^{key}:\s*\S+", text, re.MULTILINE):
                findings.append(Finding("manifest-field", "error", f"Missing manifest field: {key}", f"agent.yaml:{key}", f"Add {key} to agent.yaml."))

    explainability = root / "EXPLAINABILITY.md"
    if explainability.is_file():
        text = explainability.read_text(encoding="utf-8")
        for rule, terms in {
            "decision": ("decision", "reasoning", "how it decides"),
            "inputs": ("data source", "input", "data used"),
            "limits": ("limitation", "constraint", "known issue"),
        }.items():
            headings = [line[2:].strip().lower() for line in text.splitlines() if line.startswith("# ")]
            if not any(any(term in heading for term in terms) for heading in headings):
                findings.append(Finding("explainability-heading", "error", f"Missing explainability heading for {rule}", rule, "Add a heading containing the required concept and explain it in at least two sentences."))

    if not findings:
        findings.append(Finding("baseline", "pass", "Agent identity and explainability baseline passed", "all required files and headings present", "Keep the evidence reproducible."))
    errors = sum(finding.severity == "error" for finding in findings)
    return {
        "path": str(root),
        "status": "fail" if errors else "pass",
        "error_count": errors,
        "findings": [asdict(finding) for finding in findings],
    }
