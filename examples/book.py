import re
from pathlib import Path
from typing import Iterable, Sequence

from pdfje import XY, AutoPage, Document, Page
from pdfje.draw import Ellipse, Rect, Text
from pdfje.fonts import TrueType
from pdfje.layout import Paragraph, Rule
from pdfje.style import Style
from pdfje.units import inch, mm


def main() -> None:
    "Generate a PDF with the content of The Great Gatsby"
    Document(
        [TITLE_PAGE]
        + [AutoPage(blocks, template=create_page) for blocks in chapters()],
        style=CRIMSON,
    ).write("book.pdf")


def create_page(num: int) -> Page:
    # Add a page number at the bottom of the base page
    return BASEPAGE.add(
        Text(
            (PAGESIZE.x / 2, mm(20)), str(num), Style(size=10), align="center"
        )
    )


PAGESIZE = XY(inch(5), inch(8))
BASEPAGE = Page(
    [
        # The title in small text at the top of the page
        Text(
            (PAGESIZE.x / 2, PAGESIZE.y - mm(10)),
            "The Great Gatsby",
            Style(size=10, italic=True),
            align="center",
        ),
    ],
    size=PAGESIZE,
    margin=(mm(20), mm(20), mm(25)),
)

HEADING = Style(size=20, bold=True, line_spacing=3.5)

TITLE_PAGE = Page(
    [
        # Some nice shapes
        Rect(
            (PAGESIZE.x / 2 - 200, 275),  # use page dimensions to center it
            width=400,
            height=150,
            fill="#99aaff",
            stroke=None,
        ),
        Ellipse((PAGESIZE.x / 2, 350), 300, 100, fill="#22d388"),
        # The title and author on top of the shapes
        Text(
            (PAGESIZE.x / 2, 380),
            "The Great Gatsby",
            Style(size=30, bold=True),
            align="center",
        ),
        Text(
            (PAGESIZE.x / 2, 335),
            "F. Scott Fitzgerald",
            Style(size=14, italic=True),
            align="center",
        ),
    ],
    size=PAGESIZE,
)
CRIMSON = TrueType(
    Path(__file__).parent / "../resources/fonts/CrimsonText-Regular.ttf",
    Path(__file__).parent / "../resources/fonts/CrimsonText-Bold.ttf",
    Path(__file__).parent / "../resources/fonts/CrimsonText-Italic.ttf",
    Path(__file__).parent / "../resources/fonts/CrimsonText-BoldItalic.ttf",
)


_CHAPTER_NUMERALS = set("I II III IV V VI VII VIII IX X".split())


def chapters() -> Iterable[Sequence[Paragraph | Rule]]:
    "Book content grouped by chapters"
    buffer: list[Paragraph | Rule] = [Paragraph("Chapter I\n", HEADING)]
    for p in PARAGRAPHS:
        if p.strip() in _CHAPTER_NUMERALS:
            yield buffer
            buffer = [Paragraph(f"Chapter {p.strip()}\n", HEADING)]
        elif p.startswith("------"):
            buffer.append(Rule("#aaaaaa", (20, 10, 10)))
        else:
            buffer.append(
                Paragraph(
                    p, Style(line_spacing=1.2), align="justify", indent=20
                )
            )
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
