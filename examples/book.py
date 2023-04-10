import re
from pathlib import Path
from typing import Iterable, Sequence

from pdfje import (
    A5,
    AutoPage,
    Document,
    Ellipse,
    Line,
    Page,
    Paragraph,
    Rect,
    Rule,
    Style,
    Text,
    TrueType,
    mm,
)


def main() -> None:
    "Generate a PDF with the content of The Great Gatsby"
    Document(
        [TITLE_PAGE]
        + [AutoPage(blocks, template=create_page) for blocks in chapters()],
        style=GENTIUM,
    ).write("book.pdf")


def create_page(num: int) -> Page:
    # Add a page number at the bottom of the base page
    return BASEPAGE.add(Text((A5.x / 2, mm(20)), str(num), Style(size=8)))


BASEPAGE = Page(
    [
        # The title in small text at the top left of the page
        Text(
            (mm(20), A5.y - mm(10)),
            "The Great Gatsby",
            Style(size=8, italic=True),
        ),
        # A line at the bottom of the page
        Line((mm(20), mm(20)), (A5.x - mm(20), mm(20)), stroke="#aaaaaa"),
    ],
    size=A5,
    margin=(mm(20), mm(20), mm(25)),
)

HEADING = Style(size=20, bold=True, line_spacing=3.5)

TITLE_PAGE = Page(
    [
        # Some nice shapes
        Rect(
            (A5.x / 2 - 200, 275),  # use page dimensions to center it
            width=400,
            height=150,
            fill="#99aaff",
            stroke=None,
        ),
        Ellipse((A5.x / 2, 350), 300, 100, fill="#22d388"),
        # The title on top of the shapes
        Text((96, 380), "The Great Gatsby", Style(size=30, bold=True)),
        Text((155, 100), "F. Scott Fitzgerald", Style(size=14, bold=True)),
    ],
    size=A5,
)
GENTIUM = TrueType(
    Path(__file__).parent / "../resources/fonts/GentiumPlus-Regular.ttf",
    Path(__file__).parent / "../resources/fonts/GentiumPlus-Bold.ttf",
    Path(__file__).parent / "../resources/fonts/GentiumPlus-Italic.ttf",
    Path(__file__).parent / "../resources/fonts/GentiumPlus-BoldItalic.ttf",
)


_CHAPTER_NUMERALS = set("I II III IV V VI VII VIII IX X".split())


def chapters() -> Iterable[Sequence[Paragraph | Rule]]:
    "Book content grouped by chapters"
    buffer: list[Paragraph | Rule] = [Paragraph("Chapter I\n\n", HEADING)]
    for p in PARAGRAPHS:
        if p.strip() in _CHAPTER_NUMERALS:
            yield buffer
            buffer = [Paragraph(f"Chapter {p.strip()}\n\n", HEADING)]
        elif p.startswith("---------------------"):
            buffer.append(Rule("#aaaaaa", (20, 10, 10)))
        else:
            buffer.append(Paragraph(p))
    yield buffer


PARAGRAPHS = [
    m.replace("\n", " ")
    for m in re.split(
        r"\n\n",
        (
            Path(__file__).parent / "../resources/books/the-great-gatsby.txt"
        ).read_text()[1374:-18415],
    )
]

if __name__ == "__main__":
    main()
