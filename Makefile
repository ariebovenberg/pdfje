.PHONY: init
init:
	uv sync --locked --all-groups --all-extras

.PHONY: clean
clean:
	rm -rf .coverage .hypothesis .mypy_cache .pytest_cache .ruff_cache *.egg-info
	rm -rf dist
	find . | grep -E "(__pycache__|docs_.*$$|\.pyc|\.pyo$$)" | xargs rm -rf

.PHONY: format
format:
	uv run ruff format .

.PHONY: fix
fix:
	uv run ruff check --select I --fix .
	uv run ruff format .

.PHONY: lint
lint:
	uv run ruff check .

.PHONY: mypy
mypy:
	uv run mypy --pretty --strict src examples/
	uv run mypy --pretty tests/

.PHONY: test
test:
	uv run pytest --cov=pdfje

.PHONY: docs
docs:
	@touch docs/api.rst
	uv run make -C docs/ html

.PHONY: publish
publish:
	rm -rf dist/*
	uv build
	twine upload dist/*
