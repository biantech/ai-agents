PY ?= python3

.PHONY: test run smoke clean

test:
	$(PY) -m unittest discover -s tests -p "test_*.py" -v

run:
	$(PY) run_analysis.py

smoke:
	$(PY) run_analysis.py 3

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
