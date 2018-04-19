all: pylint

.PHONY: pylint
pylint:
	pylint -f colorized publ
