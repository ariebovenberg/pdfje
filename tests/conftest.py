from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption("--output-path", help="Output path for PDF files")


@pytest.fixture
def outfile(tmpdir, request) -> Path:
    output_path = request.config.getoption("--output-path")
    base = Path(tmpdir if output_path is None else output_path)
    base.mkdir(exist_ok=True)
    func = request.function
    return base / f"{func.__module__.replace('.', '-')}-{func.__name__}.pdf"
