import unittest

from agent_passport.adapters import NativeRuntimeAdapter, PortableJsonAdapter
from agent_passport.demo import build_demo_core


class CoreAndAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.core = build_demo_core()

    def test_two_adapters_share_same_contract(self) -> None:
        payload = {"task": "explain portability"}
        native = NativeRuntimeAdapter(self.core).execute(payload)
        portable = PortableJsonAdapter(self.core).execute(payload)
        self.assertEqual(native["answer"], portable["answer"])
        self.assertNotEqual(native["runtime"], portable["runtime"])
        self.assertEqual(native["passport_fingerprint"], portable["passport_fingerprint"])

    def test_invalid_task_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            NativeRuntimeAdapter(self.core).execute({"task": ""})


if __name__ == "__main__":
    unittest.main()
