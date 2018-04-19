all: pylint

.PHONY: pylint
pylint:
	pylint -f colorized publ

.PHONY: build
build:
	python3 setup.py sdist
	python3 setup.py bdist_wheel --universal

.PHONY: upload
upload: build
	twine upload dist/*
