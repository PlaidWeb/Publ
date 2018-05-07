all: pylint

.PHONY: pylint
pylint:
	pipenv run pylint -f colorized publ

.PHONY: build
build: pylint
	pipenv run python3 setup.py sdist
	pipenv run python3 setup.py bdist_wheel

.PHONY: clean
clean:
	rm -rf build dist

.PHONY: upload
upload: clean build
	pipenv run twine upload dist/*
