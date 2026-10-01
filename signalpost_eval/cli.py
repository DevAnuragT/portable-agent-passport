"""Command-line smoke runner for local Signalpost JSONL output."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .evaluator import evaluate_files, report_digest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate a Signalpost JSONL batch offline")
    parser.add_argument("--inputs", "--input", dest="inputs", required=True, help="input company JSONL")
    parser.add_argument("--outputs", "--output", dest="outputs", required=True, help="terminal envelope JSONL")
    parser.add_argument("--report", required=True, help="machine-readable JSON report destination")
    parser.add_argument("--strict", action="store_true", help="exit 1 when local contract checks fail")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = evaluate_files(args.inputs, args.outputs)
    except Exception as exc:
        print(f"signalpost-eval: {exc}", file=sys.stderr)
        return 2
    report = dict(report)
    report["report_digest"] = report_digest(report)
    destination = Path(args.report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "report": str(destination), "report_digest": report["report_digest"]}, sort_keys=True))
    return 1 if args.strict and not report["passed"] else 0
