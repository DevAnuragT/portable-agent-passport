import unittest

from adapters.claude_code import run as claude_run
from adapters.crewai import CrewAIPortableAgent
from adapters.lyzr import LyzrAgent
from adapters.openai_sdk import OpenAIResponsesAdapter


class ExportAdapterTests(unittest.TestCase):
    def test_all_four_framework_shapes_reach_same_core(self) -> None:
        outputs = [
            OpenAIResponsesAdapter().responses_create(input="explain portability"),
            CrewAIPortableAgent().kickoff({"task": "explain portability"}),
            claude_run("explain portability"),
            LyzrAgent().run("explain portability"),
        ]
        self.assertEqual({output["answer"] for output in outputs}, {"Demo answer: explain portability"})
        self.assertEqual({output["passport_fingerprint"] for output in outputs}, {outputs[0]["passport_fingerprint"]})


if __name__ == "__main__":
    unittest.main()
