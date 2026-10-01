"""Command-line entrypoint for offline and explicit live runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .adapters import BulkBrregAdapter, FixtureBrregAdapter, LiveBrregAdapter, LocalJsonlAdapter, MODULES
from .batch import read_jsonl, read_output_jsonl, run_batch
from .website import WebsiteEnabledAdapter, WebsiteFetcher


def _default_fixture() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "brreg_fixture.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic Signalpost company research")
    parser.add_argument("--input", required=True, help="JSONL file with one organisation_number per line")
    parser.add_argument("--output", default="-", help="JSONL output path, or - for stdout")
    parser.add_argument("--adapter", choices=("fixture", "local-jsonl", "bulk", "live"), default="fixture")
    parser.add_argument("--source", help="Fixture JSON, local JSONL, or BRREG bulk CSV/CSV.GZ path")
    parser.add_argument("--previous", help="Prior output JSONL for refresh diffs or resume")
    parser.add_argument("--resume", action="store_true", help="Reuse terminal envelopes from --previous without refetching them")
    parser.add_argument("--timeout", type=float, default=10.0, help="Live BRREG request timeout in seconds")
    parser.add_argument("--no-website", action="store_true", help="Do not fetch registry-listed static websites during live runs")
    parser.add_argument("--workers", type=int, default=1, help="Maximum number of companies researched concurrently")
    parser.add_argument("--request-budget", type=int, help="Global maximum number of network requests (live runs)")
    parser.add_argument("--modules", nargs="+", metavar="MODULE", help="Live BRREG modules (space- or comma-separated)")
    parser.add_argument("--version", action="version", version="signalpost 0.2.0")
    return parser


def _parse_modules(values: Optional[List[str]]) -> Optional[List[str]]:
    if not values:
        return None
    modules = [part.strip() for value in values for part in value.split(",") if part.strip()]
    if not modules:
        raise ValueError("--modules requires at least one module")
    unknown = sorted(set(modules) - set(MODULES))
    if unknown:
        raise ValueError("unsupported live module(s): " + ", ".join(unknown))
    if len(set(modules)) != len(modules):
        raise ValueError("--modules must not contain duplicates")
    return modules


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inputs = read_jsonl(args.input)
        if args.adapter == "fixture":
            adapter = FixtureBrregAdapter(args.source or _default_fixture())
        elif args.adapter == "local-jsonl":
            if not args.source:
                raise ValueError("--source is required for --adapter local-jsonl")
            adapter = LocalJsonlAdapter(args.source)
        elif args.adapter == "bulk":
            if not args.source:
                raise ValueError("--source is required for --adapter bulk")
            adapter = BulkBrregAdapter(args.source)
        else:
            adapter = LiveBrregAdapter(args.timeout, modules=_parse_modules(args.modules))
            if not args.no_website:
                adapter = WebsiteEnabledAdapter(adapter, WebsiteFetcher(args.timeout))
        if args.adapter != "live" and args.modules:
            raise ValueError("--modules is only valid with --adapter live")
        if args.resume and not args.previous:
            raise ValueError("--resume requires --previous")
        previous = read_output_jsonl(args.previous) if args.previous else None
        envelopes = run_batch(
            inputs,
            adapter,
            None if args.output == "-" else args.output,
            previous,
            args.resume,
            workers=args.workers,
            request_budget=args.request_budget,
        )
        if args.output == "-":
            for envelope in envelopes:
                print(envelope.json())
        print(f"signalpost: wrote {len(envelopes)} terminal envelopes", file=sys.stderr)
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"signalpost: error: {exc}", file=sys.stderr)
        return 2
