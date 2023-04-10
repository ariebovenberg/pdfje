.PHONY: init
init:
	poetry install
	pip install -r docs/requirements.txt

.PHONY: clean
clean:
	rm -rf .coverage .hypothesis .mypy_cache .pytest_cache .tox *.egg-info
	rm -rf dist
	find . | grep -E "(__pycache__|docs_.*$$|\.pyc|\.pyo$$)" | xargs rm -rf

.PHONY: isort
isort:
	isort .

.PHONY: format
format:
	black .

.PHONY: fix
fix: isort format

.PHONY: lint
lint:
	flake8 .

.PHONY: mypy
mypy:
	mypy --pretty src tests examples/

.PHONY: test
test:
	pytest --cov=pdfje

.PHONY: docs
docs:
	@touch docs/api.rst
	make -C docs/ html

.PHONY: publish
publish:
	rm -rf dist/*
	poetry build
	twine upload dist/*
