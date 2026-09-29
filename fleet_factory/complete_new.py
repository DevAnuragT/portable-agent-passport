#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'passport-fleet'

def write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.rstrip()+'\n', encoding='utf-8')

def main():
    count=0
    for root in sorted(ROOT.iterdir()):
        meta_path=root/'metadata.json'
        if not root.is_dir() or not meta_path.exists(): continue
        m=json.loads(meta_path.read_text())
        slug=m['slug']; title=m['title']; tool=f'audit-{slug}'; skill=f'{slug}-skill'
        agent_yaml='\n'.join([
            'spec_version: "0.1.0"', f'name: {slug}', 'version: 0.1.0', f'description: {json.dumps(m["description"])}',
            'skills:', f'  - {skill}', 'tools:', f'  - {tool}', 'tags:', f'  - {json.dumps(m["category"].lower().replace(" ", "-"))}', '  - evidence-driven', ''])
        write(root/'agent.yaml', agent_yaml)
        write(root/'SOUL.md', f'''# Identity\n\nI am {title}, a focused evidence-driven agent. I inspect caller-provided inputs, apply transparent domain rules, and return findings that a human can review.\n\n## Core Identity\n\nMy purpose is to {m['description'].lower()}\n\n## Communication Style\n\nI report decisions, evidence, and limitations separately. I never imply that a deterministic review is a certification or an official platform result.\n\n## Values & Principles\n\nI value reproducibility, bounded inputs, privacy-safe processing, and human ownership of consequential actions.\n\n## Domain Expertise\n\nI specialise in the domain rules documented in this repository's `agent.py`, tests, examples, and skill.\n''')
        write(root/'RULES.md', '''# Rules\n\n## Must Always\n\n- Validate input types and bounds before analysis.\n- Report the rule, evidence location, and remediation for every finding.\n- Keep analysis deterministic, local, and read-only.\n- Escalate consequential decisions to a qualified human.\n\n## Must Never\n\n- Invent evidence or claim official verification.\n- Read arbitrary files, call remote services, or request credentials.\n- Treat missing or malformed evidence as a pass.\n\n## Output Constraints\n\nReturn JSON-safe findings with an explicit status, domain evidence, and limitations.\n\n## Safety and Ethics\n\nThis agent is decision support and is not professional, legal, medical, financial, security, or regulatory certification.\n''')
        write(root/'DUTIES.md', '''# Maker\n\nThe Maker defines the domain algorithm and prepares evidence-backed results.\n\n# Checker\n\nThe Checker reviews the result, verifies evidence coverage, and rejects unsupported claims.\n''')
        write(root/'AGENTS.md', f'''# Agent instructions\n\nRun `{title}` using the documented JSON payload. Preserve deterministic behaviour, cite observed evidence, and state the limitations from `metadata.json`.\n''')
        write(root/'EXPLAINABILITY.md', f'''# Decision and Reasoning\n\n{m['decision']} The implementation returns structured findings so a reviewer can see how each result was derived.\n\n# Inputs and Data Sources\n\n{m['inputs']} The only data source is the caller-provided payload plus the checked-in rules and code; no network or private-file access is used.\n\n# Known Limitations and Constraints\n\n{m['limitations']} The result is a bounded pre-review aid and must not be presented as professional certification or an official HiDevs result.\n''')
        write(root/'README.md', f'''# {title}\n\n{m['description']}\n\n## Architecture\n\n```text\nJSON payload → domain algorithm → evidence-backed findings → human review\n                              └→ OpenAI / CrewAI / Claude Code / Lyzr export surfaces\n```\n\nThe core implementation is `agent.py` and exposes `analyze(payload)`. Tests include valid, malformed, boundary, and domain-specific cases.\n\n## Run\n\n```bash\npython3 agent.py examples/good-input.json\npython3 -m unittest discover -s tests -v\npython3 tools/{tool}.py examples/good-input.json\n```\n\n## Limitations\n\n{m['limitations']}\n''')
        schema=json.dumps(m['input_schema'], separators=(',', ': '))
        write(root/f'skills/{skill}/SKILL.md', f'''---\nname: {skill}\ndescription: Apply {title.lower()} rules and explain evidence-backed remediation.\n---\n\n# {title}\n\nValidate the input contract, run the deterministic analyzer, report every finding with evidence, and keep limitations visible.\n''')
        write(root/f'tools/{tool}.yaml', f'''name: {tool}\ndescription: Run the {title} deterministic analyzer\nversion: 0.1.0\ninput_schema:\n  type: object\n  properties:\n    payload:\n      type: object\n      description: JSON payload matching the agent input contract\n  required: [payload]\noutput_schema:\n  type: object\n  properties:\n    findings: {{type: array}}\n    valid: {{type: boolean}}\nimplementation:\n  type: script\n  path: {tool}.py\n  runtime: python3\n''')
        write(root/f'tools/{tool}.py', f'''import json\nimport sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nfrom agent import analyze\nsource = Path(sys.argv[1]) if len(sys.argv) > 1 else None\npayload = json.loads(source.read_text(encoding="utf-8") if source else sys.stdin.read())\nprint(json.dumps(analyze(payload), indent=2, sort_keys=True))\n''')
        write(root/'adapters/base.py', '''from agent import analyze\n\ndef execute(payload):\n    return analyze(payload)\n''')
        for name in ('openai','crewai','claude_code','lyzr'):
            write(root/f'adapters/{name}_adapter.py', '''from .base import execute\n\ndef run(payload):\n    return execute(payload)\n''')
        count+=1
    print('completed',count,'new agent repositories')

if __name__=='__main__': main()
