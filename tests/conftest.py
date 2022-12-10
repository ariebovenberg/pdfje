from pathlib import Path

import pytest

from pdfje.fonts.common import TrueType

RESOURCES = Path(__file__).parent / "../resources"


def pytest_addoption(parser):
    parser.addoption("--output-path", help="Output path for PDF files")
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )


@pytest.fixture
def outfile(tmpdir, request) -> Path:
    base = Path(request.config.getoption("--output-path") or tmpdir)
    base.mkdir(exist_ok=True)
    func = request.function
    return (
        base
        / "-".join(
            [func.__module__.removeprefix("tests."), func.__qualname__]
        ).replace(".", "-")
    ).with_suffix(".pdf")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


@pytest.fixture(scope="session")
def dejavu() -> TrueType:
    return TrueType(
        RESOURCES / "fonts/DejaVuSansCondensed.ttf",
        RESOURCES / "fonts/DejaVuSansCondensed-Bold.ttf",
        RESOURCES / "fonts/DejaVuSansCondensed-Oblique.ttf",
        RESOURCES / "fonts/DejaVuSansCondensed-BoldOblique.ttf",
    )


@pytest.fixture(scope="session")
def gentium() -> TrueType:
    return TrueType(
        RESOURCES / "fonts/GentiumPlus-Regular.ttf",
        RESOURCES / "fonts/GentiumPlus-Bold.ttf",
        RESOURCES / "fonts/GentiumPlus-Italic.ttf",
        RESOURCES / "fonts/GentiumPlus-BoldItalic.ttf",
    )
