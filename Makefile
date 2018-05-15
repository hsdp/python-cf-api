VENV := virtualenv
PIPNOCACHE := --no-cache-dir

PY2_EXE := python
PY2_ENV := env
PY2_VENV := $(VENV)
PY2_ACT := . $(PY2_ENV)/bin/activate &&

PY3_EXE := python3
PY3_ENV := env3
PY3_VENV := $(VENV) -p python3
PY3_ACT := . $(PY3_ENV)/bin/activate &&

.PHONY: clean
clean:
	rm -r $(PY2_ENV) || :
	rm -r $(PY3_ENV) || :

.PHONY: install
install:
	[[ ! -f $(PY2_ENV)/bin/activate ]] && $(PY2_VENV) $(PY2_ENV) || :
	[[ ! -f $(PY3_ENV)/bin/activate ]] && $(PY3_VENV) $(PY3_ENV) || :
	$(PY2_ACT) pip $(PIPNOCACHE) install -r requirements.txt
	$(PY3_ACT) pip $(PIPNOCACHE) install -r requirements.txt

.PHONY: install-dev
install-dev: install
	$(PY2_ACT) pip $(PIPNOCACHE) install -r requirements-dev.txt
	$(PY3_ACT) pip $(PIPNOCACHE) install -r requirements-dev.txt

.PHONY: test
test: install-dev
	$(PY2_ACT) nose2 -v 
	$(PY3_ACT) nose2 -v

.PHONY: example
example:
	$(PY2_ACT) cd examples && PYTHONPATH=.. $(PY2_EXE) $(EXAMPLE_NAME).py
	$(PY3_ACT) cd examples && PYTHONPATH=.. $(PY3_EXE) $(EXAMPLE_NAME).py

.PHONY: deploy
deploy: clean test
	python setup.py sdist upload --repository=https://upload.pypi.org/legacy/
