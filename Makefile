SHELL := /bin/bash

PACKAGENAME := cf_api
PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
NOSE ?= $(PYTHON) -m nose
NOSEFLAGS ?= --nologcapture
OPEN := $(shell which xdg-open || which open)

.PHONY: test
test: deps
	$(NOSE) -v --with-coverage --cover-html --cover-package $(PACKAGENAME) --cover-erase $(NOSEFLAGS) && $(OPEN) cover/index.html

.PHONY: deps
deps:
	$(PIP) install requests responses coverage nose pdoc markdown2

.PHONY: sdist
build: test
	$(PYTHON) setup.py sdist

.PHONY: docs
docs: deps
	$(PYTHON) -m markdown2 -v -x code-friendly -x tables -x fenced-code-blocks README.md > readme.m.html
	PYTHONPATH=./ pdoc --html $(PACKAGENAME) --overwrite && $(OPEN) $(PACKAGENAME).m.html
