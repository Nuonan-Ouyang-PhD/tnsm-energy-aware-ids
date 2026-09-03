PYTHON ?= python3

.PHONY: test snapshot preflight smoke formal-gate

test:
	PYTHONPATH=src $(PYTHON) -m compileall -q src tests
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

snapshot:
	PYTHONPATH=src $(PYTHON) -m tnsm_exp snapshot

preflight:
	PYTHONPATH=src $(PYTHON) -m tnsm_exp preflight

smoke:
	PYTHONPATH=src $(PYTHON) -m tnsm_exp smoke

formal-gate:
	PYTHONPATH=src $(PYTHON) -m tnsm_exp formal-gate

