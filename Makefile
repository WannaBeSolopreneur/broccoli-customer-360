# make all: generate data, build the warehouse, run checks and tests, write reports and charts.
PY ?= .venv/bin/python

.PHONY: setup generate build quality test report diagram ask all clean

setup:
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements.txt

generate:
	$(PY) -m c360.generate

build:
	$(PY) -m c360.warehouse

quality:
	$(PY) -m c360.quality

test:
	$(PY) -m pytest

report:
	$(PY) -m c360.report

diagram:
	$(PY) -m c360.diagram

ask:
	$(PY) -m c360.ask

all: generate build quality test report diagram

clean:
	rm -rf data warehouse .pytest_cache
