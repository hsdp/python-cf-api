SHELL := /bin/bash

PACKAGENAME := cf_api
PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
NOSE ?= $(PYTHON) -m nose
NOSEFLAGS ?= -v -s --with-coverage --cover-html --cover-package $(PACKAGENAME) --cover-erase

.PHONY: test
test: deps
	$(NOSE) $(NOSEFLAGS)

.PHONY: deps
deps:
	$(PIP) install requests responses coverage nose pdoc

.PHONY: sdist
build: test
	$(PYTHON) setup.py sdist

.PHONY: docs
docs: deps
	PYTHONPATH=./ pdoc --html $(PACKAGENAME) --overwrite && xdg-open $(PACKAGENAME).m.html
