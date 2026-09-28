.PHONY: test verify demo

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

verify:
	PYTHONPATH=src python3 -m agent_passport verify

demo:
	PYTHONPATH=src python3 -m agent_passport run "summarise the portability goal" --runtime portable-json
