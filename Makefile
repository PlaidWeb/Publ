all: setup format mypy cov pylint flake8

.PHONY: setup
setup:
	poetry install

.PHONY: format
format:
	poetry run isort -y
	poetry run autopep8 -r --in-place .

.PHONY: pylint
pylint:
	poetry run pylint publ tests

.PHONY: flake8
flake8:
	poetry run flake8

.PHONY: mypy
mypy:
	poetry run mypy -p publ -m tests --ignore-missing-imports

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
	poetry run coverage run -m pytest -Werror

.PHONY: cov
cov: test
	poetry run coverage html
	poetry run coverage report

.PHONY: version
version:
	# Kind of a hacky way to get the version updated, until the poetry folks
	# settle on a better approach
	printf '""" version """\n__version__ = "%s"\n' \
		`poetry version | cut -f2 -d\ ` > publ/__version__.py

.PHONY: build
build: version preflight pylint flake8
	poetry build

.PHONY: clean
clean:
	rm -rf dist .mypy_cache .pytest_cache .coverage
	find . -name __pycache__ -delete

.PHONY: upload
upload: clean test build
	poetry publish
