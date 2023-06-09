from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from pdfje import XY, AutoPage, Column, Document, Page
from pdfje.draw import Text
from pdfje.fonts import TrueType
from pdfje.layout import Paragraph
from pdfje.layout.paragraph import LinebreakParams
from pdfje.style import Span, Style, italic
from pdfje.units import inch, mm


def main() -> None:
    Document(
        [
            AutoPage(
                [*content, *(replace(p, optimal=False) for p in content)],
                template=TEMPLATE,
            )
        ],
        style=CRIMSON,
    ).write("optimal-vs-firstfit.pdf")


PAGESIZE = XY(inch(10), inch(8))
MARGIN = mm(16)
TEMPLATE = Page(
    [
        # The title in small text at the top of the page
        Text(
            (PAGESIZE.x / 4, PAGESIZE.y - mm(5)),
            "Optimal",
            Style(size=12, bold=True),
            align="center",
        ),
        Text(
            (PAGESIZE.x * 0.75, PAGESIZE.y - mm(5)),
            "Fast",
            Style(size=12, bold=True),
            align="center",
        ),
    ],
    size=PAGESIZE,
    columns=[
        Column(
            (MARGIN, MARGIN),
            PAGESIZE.x / 2 - MARGIN * 2,
            PAGESIZE.y - MARGIN * 2,
        ),
        Column(
            (PAGESIZE.x / 2 + MARGIN, MARGIN),
            PAGESIZE.x / 2 - MARGIN * 2,
            PAGESIZE.y - MARGIN * 2,
        ),
    ],
)

CRIMSON = TrueType(
    Path(__file__).parent / "../resources/fonts/CrimsonText-Regular.ttf",
    Path(__file__).parent / "../resources/fonts/CrimsonText-Bold.ttf",
    Path(__file__).parent / "../resources/fonts/CrimsonText-Italic.ttf",
    Path(__file__).parent / "../resources/fonts/CrimsonText-BoldItalic.ttf",
)


def flatten_newlines(txt: str) -> str:
    return "\n".join(s.replace("\n", " ") for s in txt.split("\n\n"))


# Extract from https://www.gutenberg.org/ebooks/1661
content = [
    Paragraph(
        [
            flatten_newlines(
                """\
“To the man who loves art for its own sake,” remarked Sherlock
Holmes, tossing aside the advertisement sheet of"""
            ),
            Span(" The Daily Telegraph", italic),
            flatten_newlines(
                """, “it is
frequently in its least important and lowliest manifestations that the
keenest pleasure is to be derived. It is pleasant to me to observe,
Watson, that you have so far grasped this truth that in these little
records of our cases which you have been good enough to draw up, and, I
am bound to say, occasionally to embellish, you have given prominence
not so much to the many """
            ),
            Span("causes célèbres", italic),
            flatten_newlines(
                """ and sensational trials in
which I have figured but rather to those incidents which may have been
trivial in themselves, but which have given room for those faculties of
deduction and of logical synthesis which I have made my special
province.”"""
            ),
        ],
        align="justify",
        indent=0,
        optimal=LinebreakParams(
            tolerance=1,
            hyphen_penalty=0,
        ),
        avoid_orphans=False,
    ),
    Paragraph(
        [
            flatten_newlines(
                """\
“And yet,” said I, smiling, “I cannot quite hold myself absolved from
the charge of sensationalism which has been urged against my records.”

“You have erred, perhaps,” he observed, taking up a glowing cinder with
the tongs and lighting with it the long cherry-wood pipe which was wont
to replace his clay when he was in a disputatious rather than a
meditative mood—“you have erred perhaps in attempting to put colour and
life into each of your statements instead of confining yourself to the
task of placing upon record that severe reasoning from cause to effect
which is really the only notable feature about the thing.”

“It seems to me that I have done you full justice in the matter,” I
remarked with some coldness, for I was repelled by the egotism which I
had more than once observed to be a strong factor in my friend’s
singular character.




"""
            ),
        ],
        align="justify",
        indent=18,
        optimal=LinebreakParams(
            tolerance=3,
            hyphen_penalty=1000,
        ),
        avoid_orphans=False,
    ),
]


if __name__ == "__main__":
    main()
