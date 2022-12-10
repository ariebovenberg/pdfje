from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption("--output-path", help="Output path for PDF files")
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )


@pytest.fixture
def outfile(tmpdir, request) -> Path:
    output_path = request.config.getoption("--output-path")
    base = Path(tmpdir if output_path is None else output_path)
    base.mkdir(exist_ok=True)
    func = request.function
    return base / f"{func.__module__.replace('.', '-')}-{func.__name__}.pdf"


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
