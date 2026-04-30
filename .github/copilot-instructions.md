# Copilot Instructions for pdfje

## What is pdfje?

A declarative, pure-Python PDF writer library. Users describe documents with immutable data structures; pdfje handles layout, typesetting, and PDF generation. No mutation-based APIs — everything is built from frozen dataclasses.

## Build, test, and lint

```bash
poetry install                        # install all deps
poetry install -E fonts -E hyphens    # include optional extras

pytest                                # run tests (slow tests skipped by default)
pytest tests/test_atoms.py            # run a single test file
pytest tests/test_atoms.py::TestName  # run a single test class/function
pytest --runslow                      # include slow tests
pytest --output-path=output/          # write generated PDFs to a directory

make fix                              # auto-format (black + isort)
make lint                             # flake8
make mypy                             # type checking (strict on src/, relaxed on tests/)

tox                                   # full CI matrix across Python 3.8–3.12
```

## Architecture

### Processing pipeline

`Document` → `Page`/`AutoPage` → layout engine → typesetter → PDF atoms → binary output

- **`document.py`** — Entry point. `Document.write()` orchestrates the pipeline, iterating pages and collecting PDF objects.
- **`page.py`** — `Page` holds explicit drawings; `AutoPage` (in `layout/pages.py`) flows block content across pages/columns automatically.
- **`layout/`** — Page layout engine. `Block` is the abstract base for content that flows into columns (e.g. `Paragraph`, `Rule`). `ColumnFill`/`PageFill` track how space is consumed.
- **`typeset/`** — Text shaping and line breaking. Implements Knuth-Plass optimum-fit (`knuth_plass.py`, `optimum.py`) and a first-fit fallback (`firstfit.py`). `state.py` manages the typesetting state machine (font, color, line spacing) via `Command` objects.
- **`atoms.py`** — Low-level PDF object model (Name, Dictionary, Stream, Ref, etc.). Directly maps to PDF spec (PDF 32000-1:2008). All atoms implement `write() -> Iterable[bytes]`.
- **`fonts/`** — `builtins.py` has the 5 standard PDF typefaces; `embed.py` handles TrueType font subsetting (optional `fonttools` dependency).
- **`resources.py`** — Tracks fonts used in a document, deduplicates, and assigns PDF object IDs.
- **`draw.py`** — Drawing primitives (Line, Rect, Circle, Text, etc.) that implement the `Drawing` protocol.
- **`style.py`** — `Style` (partial) and `StyleFull` (complete) for text styling. Styles compose with `|` operator. `Span` nests styled text.

### Key design patterns

- **Frozen dataclasses everywhere** — All domain objects are `@dataclass(frozen=True, slots=True)`. Use `setattr_frozen` (aliased `object.__setattr__`) in `__init__` to set fields on frozen instances with custom validation.
- **`@final` on concrete classes** — Leaf classes are marked `@final`.
- **Streaming output** — PDF generation uses `Iterator[bytes]` / `Iterable[bytes]` (aliased as `Streamable`) throughout, enabling lazy generation.
- **Type aliases in `common.py`** — `Pt = float`, `Char = str`, `Pos = int`, `HexColor = str`, `Streamable = Iterable[bytes]`. Use these for domain clarity.
- **`pipe()` for function composition** — Heavily overloaded for type-safe function pipelines.
- **`StyleLike` union type** — Accepts `Style | RGB | Typeface | HexColor` wherever styles are needed, with `Style.parse()` for normalization.
- **Operator patching to avoid circular imports** — `__or__`/`__ror__` on `RGB` and `Typeface` are defined in `style.py` and patched onto the classes at module load under `if not TYPE_CHECKING`.

## Conventions

- Every Python file starts with `from __future__ import annotations` (enforced by isort `add_imports`).
- Line length is 79 characters (black + isort).
- Source layout: `src/pdfje/` (library), `tests/` (mirrors source structure), `examples/`.
- `src/pdfje/vendor/` contains vendored third-party code — excluded from type checking, linting, and slotscheck.
- Type checking is strict (`--strict`) on `src/` and `examples/`, relaxed on `tests/`.
- Coverage target is 99%. `vendor/`, `__repr__`, `overload`, `NotImplementedError`, and `TYPE_CHECKING` blocks are excluded.
- Tests use `hypothesis` for property-based testing and `pytest-benchmark` for performance (disabled by default).
- The `@pytest.mark.slow` marker gates expensive tests behind `--runslow`.
- Python 3.10+ — no compatibility shims needed. Uses `itertools.pairwise`, `functools.cache` directly.
- Optional dependencies: `fonttools` (font embedding via `pdfje[fonts]`), `pyphen` (hyphenation via `pdfje[hyphens]`). Code must work without them.
