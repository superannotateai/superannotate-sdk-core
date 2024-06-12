.PHONY: help coverage linter install mypy test validate

help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  help       to show this help"
	@echo "  validate   to make source code validation"

validate:
	tox -e pre-commit
