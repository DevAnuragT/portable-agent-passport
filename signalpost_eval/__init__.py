"""Offline evaluation for Signalpost JSONL terminal envelopes.

This package intentionally has no dependency on the Signalpost implementation.  It
validates the documented wire contract so it can be installed and run separately
from an agent submission.
"""

from .evaluator import EvaluationError, evaluate_batch, evaluate_files, read_jsonl

__all__ = ["EvaluationError", "evaluate_batch", "evaluate_files", "read_jsonl"]
