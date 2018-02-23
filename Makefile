.PHONY: test deps deps-dev clean deploy

clean:
	rm -r env || :
	rm -r env3 || :

deps:
	[[ ! -f env/bin/activate ]] && virtualenv env || :
	[[ ! -f env3/bin/activate ]] && virtualenv -p python3 env3 || :
	. env/bin/activate && pip install -r requirements.txt ; deactivate
	. env3/bin/activate && pip install -r requirements.txt ; deactivate

deps-dev:
	[[ ! -f env/bin/activate ]] && virtualenv env || :
	[[ ! -f env3/bin/activate ]] && virtualenv -p python3 env3 || :
	. env/bin/activate && pip install -r requirements-dev.txt ; deactivate
	. env3/bin/activate && pip install -r requirements-dev.txt ; deactivate

test: deps deps-dev
	. env/bin/activate && nose2 -v ; deactivate
	. env3/bin/activate && nose2 -v ; deactivate

deploy: clean test
	python setup.py sdist upload --repository=https://upload.pypi.org/legacy/
