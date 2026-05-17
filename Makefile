PYTHON ?= python3

.PHONY: dev test seed trigger-incident

dev:
	$(PYTHON) -m pulse.cli seed
	$(PYTHON) -m uvicorn pulse.api.main:app --reload

test:
	$(PYTHON) -m pytest

seed:
	$(PYTHON) -m pulse.cli seed

trigger-incident:
	$(PYTHON) -m pulse.cli trigger-incident
