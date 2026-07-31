# Peter Lynch PEG analysis agent - developer shortcuts.
#
# Usage:
#   make test    # run the unit-test suite (regression)
#   make run     # run the full 50-stock analysis
#   make smoke   # quick smoke test on the first 5 codes
#   make clean   # remove __pycache__ and cached artifacts

PY ?= python3

.PHONY: test run smoke clean

test:
	$(PY) -m unittest discover -s tests -p "test_*.py" -v

run:
	$(PY) run_analysis.py

smoke:
	$(PY) run_analysis.py 5

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
