"""Command-line entry point for the offline passport demonstration."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .adapters import NativeRuntimeAdapter, PortableJsonAdapter
from .demo import build_demo_core
from .verify import run_checks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run and verify the Portable Agent Passport demo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run the demo agent")
    run_parser.add_argument("task", help="task for the agent")
    run_parser.add_argument("--runtime", choices=("native", "portable-json"), default="native")

    subparsers.add_parser("verify", help="run all offline verification checks")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    core = build_demo_core()
    if args.command == "run":
        adapter = NativeRuntimeAdapter(core) if args.runtime == "native" else PortableJsonAdapter(core)
        print(json.dumps(adapter.execute({"task": args.task}), indent=2, sort_keys=True))
        return 0

    results = run_checks(core)
    print(json.dumps([result.__dict__ for result in results], indent=2, sort_keys=True))
    return 0 if all(result.passed for result in results) else 1
