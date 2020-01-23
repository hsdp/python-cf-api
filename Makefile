SHELL := /bin/sh
DOCKERIMAGE := python-cf-api:latest
PY2BIN := python2
PY3BIN := python3

.PHONY: test
test:
	make docker-run CMD='\
		$(PY2BIN) -m nose2 -v && \
		$(PY3BIN) -m nose2 -v'

.PHONY: deploy
deploy: test
	make docker-run CMD='\
	rm -r dist/ || : && \
	$(PY3BIN) setup.py sdist && \
	$(PY3BIN) -m twine upload \
		--verbose \
		--repository-url https://upload.pypi.org/legacy/ \
		--username '$(PYPI_USERNAME)' \
		--password '$(PYPI_PASSWORD)' \
		dist/cf_api-*'

.PHONY: docker-image
docker-image:
	docker build -t $(DOCKERIMAGE) .

.PHONY: docker-run
docker-run: docker-image
	docker run \
		--rm -it \
		-v $(PWD):/src \
		-w /src \
		$(DOCKERIMAGE) \
		/bin/sh -c '$(CMD)'
