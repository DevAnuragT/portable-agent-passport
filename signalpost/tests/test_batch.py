import json
import tempfile
import unittest
from pathlib import Path

from signalpost.adapters import FixtureBrregAdapter
from signalpost.batch import read_jsonl, run_batch
from signalpost.models import Availability


FIXTURE = Path(__file__).parents[1] / "src" / "signalpost" / "fixtures" / "brreg_fixture.json"
INPUT = Path(__file__).parents[1] / "examples" / "input.jsonl"


class BatchTests(unittest.TestCase):
    def test_every_input_gets_one_terminal_envelope_and_replay_is_identical(self):
        inputs = read_jsonl(INPUT)
        adapter = FixtureBrregAdapter(FIXTURE)
        first = run_batch(inputs, adapter)
        second = run_batch(inputs, FixtureBrregAdapter(FIXTURE))
        self.assertEqual(len(first), len(inputs))
        self.assertEqual([item.state for item in first], [Availability.AVAILABLE, Availability.AVAILABLE, Availability.NOT_AVAILABLE])
        self.assertEqual([item.json() for item in first], [item.json() for item in second])
        self.assertTrue(all(item.run.terminal_status in Availability for item in first))

    def test_output_is_atomic_jsonl(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "profiles.jsonl"
            run_batch(read_jsonl(INPUT), FixtureBrregAdapter(FIXTURE), output)
            lines = output.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 3)
        rows = [json.loads(line) for line in lines]
        self.assertEqual({row["organisation_number"] for row in rows}, {"923609016", "974760673", "123456785"})
        for row in rows:
            self.assertEqual(row["state"], row["run"]["terminal_status"])
            evidence_ids = {item["id"] for item in row["evidence"]}
            snapshot_ids = {item["id"] for item in row["snapshots"]}
            self.assertTrue(all(set(claim["evidence_ids"]) <= evidence_ids for claim in row["claims"]))
            self.assertTrue(all(item["snapshot_id"] in snapshot_ids for item in row["evidence"] if item["snapshot_id"]))


if __name__ == "__main__":
    unittest.main()
