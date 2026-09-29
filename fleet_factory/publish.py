#!/usr/bin/env python3
"""Publish each validated fleet member as a separate public GitHub repository."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
FLEET = ROOT / "passport-fleet"
OWNER = "DevAnuragT"


def run(*args: str, cwd: Path | None = None) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def main() -> None:
    index = json.loads((FLEET / "FLEET_INDEX.json").read_text())
    published = []
    for item in index:
        slug = item["slug"]
        path = FLEET / slug
        repo = f"agent-{slug}"
        run("git", "init", "-b", "main", cwd=path)
        run("git", "add", ".", cwd=path)
        run("git", "-c", "user.name=Anurag Thakur", "-c", "user.email=anuragthakur2102@gmail.com", "commit", "-m", "feat: add portable domain agent", cwd=path)
        url = run("gh", "repo", "create", f"{OWNER}/{repo}", "--public", "--source", str(path), "--remote", "origin", "--push", "--description", item["title"], cwd=ROOT)
        published.append({"slug": slug, "repo": f"{OWNER}/{repo}", "url": url})
        print(f"published {repo}")
    (ROOT / "fleet_factory" / "published.json").write_text(json.dumps(published, indent=2) + "\n")


if __name__ == "__main__":
    main()
