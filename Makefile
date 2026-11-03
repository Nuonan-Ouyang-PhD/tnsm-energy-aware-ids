PYTHON ?= python3

.PHONY: test snapshot preflight smoke formal-gate audit test-scheduler check-submission

audit:
	$(PYTHON) experiments/adaptive_scheduler_v1/reward_audit.py --check
	$(PYTHON) -m unittest discover -s experiments/adaptive_scheduler_v1 -p test_reward_audit.py -v

test-scheduler:
	PYTHONPATH=experiments/adaptive_scheduler_v1 $(PYTHON) -m unittest scheduler.test_scheduler -v

check-submission:
	$(PYTHON) scripts/check_submission.py

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

