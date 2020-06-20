all: setup format mypy cov pylint flake8

.PHONY: setup
setup:
	pipenv run which coverage || pipenv install --dev

.PHONY: format
format:
	pipenv run isort -y
	pipenv run autopep8 -r --in-place .

.PHONY: pylint
pylint:
	pipenv run pylint publ tests

.PHONY: flake8
flake8:
	pipenv run flake8

.PHONY: mypy
mypy:
	pipenv run mypy -p publ -m tests --ignore-missing-imports

.PHONY: preflight
preflight:
	@echo "Checking commit status..."
	@git status --porcelain | grep -q . \
		&& echo "You have uncommitted changes" 1>&2 \
		&& exit 1 || exit 0
	@echo "Checking branch..."
	@[ "$(shell git rev-parse --abbrev-ref HEAD)" != "main" ] \
		&& echo "Can only build from main" 1>&2 \
		&& exit 1 || exit 0
	@echo "Checking upstream..."
	@git fetch \
		&& [ "$(shell git rev-parse main)" != "$(shell git rev-parse main@{upstream})" ] \
		&& echo "main branch differs from upstream" 1>&2 \
		&& exit 1 || exit 0

.PHONY: test
test:
	pipenv run coverage run -m pytest -Werror

.PHONY: cov
cov: test
	pipenv run coverage html
	pipenv run coverage report

.PHONY: build
build: preflight pylint flake8
	pipenv run python3 setup.py sdist
	pipenv run python3 setup.py bdist_wheel

.PHONY: clean
clean:
	rm -rf build dist .mypy_cache __pycache__

.PHONY: upload
upload: clean test build
	pipenv run twine upload dist/*
