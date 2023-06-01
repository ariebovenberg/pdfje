from pathlib import Path

from pdfje import XY, AutoPage, Column, Document, Page
from pdfje.draw import Text
from pdfje.fonts import TrueType
from pdfje.layout import Paragraph
from pdfje.style import Span, Style, italic
from pdfje.units import inch, mm


def main() -> None:
    Document([AutoPage(chapter, template=TEMPLATE)], style=CRIMSON).write(
        "sample.pdf"
    )


PAGESIZE = XY(inch(8), inch(3.6))
TEMPLATE = Page(
    [
        # The title in small text at the top of the page
        Text(
            (PAGESIZE.x / 2, PAGESIZE.y - mm(5)),
            "The Adventures of Sherlock Holmes",
            Style(size=10, italic=True),
            align="center",
        ),
    ],
    size=PAGESIZE,
    columns=[
        Column(
            (mm(15), mm(15)),
            PAGESIZE.x / 2 - mm(30),
            PAGESIZE.y - mm(30),
        ),
        Column(
            (PAGESIZE.x / 2 + mm(15), mm(15)),
            PAGESIZE.x / 2 - mm(30),
            PAGESIZE.y - mm(30),
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
chapter = Paragraph(
    [
        flatten_newlines(
            """“To the man who loves art for its own sake,” remarked Sherlock
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
province.”

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

“No, it is not selfishness or conceit,” said he, answering, as was his
wont, my thoughts rather than my words. “If I claim full justice for my
art, it is because it is an impersonal thing—a thing beyond myself.
Crime is common. Logic is rare. Therefore it is upon the logic rather
than upon the crime that you should dwell. You have degraded what
should have been a course of lectures into a series of tales.”

It was a cold morning of the early spring, and we sat after breakfast
on either side of a cheery fire in the old room at Baker Street. A
thick fog rolled down between the lines of dun-coloured houses, and the
opposing windows loomed like dark, shapeless blurs through the heavy
yellow wreaths. Our gas was lit and shone on the white cloth and
glimmer of china and metal, for the table had not been cleared yet.
Sherlock Holmes had been silent all the morning, dipping continuously
into the advertisement columns of a succession of papers until at last,
having apparently given up his search, he had emerged in no very sweet
temper to lecture me upon my literary shortcomings.

“At the same time,” he remarked after a pause, during which he had sat
puffing at his long pipe and gazing down into the fire, “you can hardly
be open to a charge of sensationalism, for out of these cases which you
have been so kind as to interest yourself in, a fair proportion do not
treat of crime, in its legal sense, at all. The small matter in which I
endeavoured to help the King of Bohemia, the singular experience of
Miss Mary Sutherland, the problem connected with the man with the
twisted lip, and the incident of the noble bachelor, were all matters
which are outside the pale of the law. But in avoiding the sensational,
I fear that you may have bordered on the trivial.”

“The end may have been so,” I answered, “but the methods I hold to have
been novel and of interest.”

“Pshaw, my dear fellow, what do the public, the great unobservant
public, who could hardly tell a weaver by his tooth or a compositor by
his left thumb, care about the finer shades of analysis and deduction!
But, indeed, if you are trivial, I cannot blame you, for the days of
the great cases are past. Man, or at least criminal man, has lost all
enterprise and originality. As to my own little practice, it seems to
be degenerating into an agency for recovering lost lead pencils and
giving advice to young ladies from boarding-schools. I think that I
have touched bottom at last, however. This note I had this morning
marks my zero-point, I fancy. Read it!” He tossed a crumpled letter
across to me.
“Pshaw, my dear fellow, what do the public, the great unobservant
public, who could hardly tell a weaver by his tooth or a compositor by
his left thumb, care about the finer shades of analysis and deduction!
But, indeed, if you are trivial, I cannot blame you, for the days of
the great cases are past. Man, or at least criminal man, has lost all
enterprise and originality. As to my own little practice, it seems to
be degenerating into an agency for recovering lost lead pencils and
giving advice to young ladies from boarding-schools. I think that I
have touched bottom at last, however. This note I had this morning
marks my zero-point, I fancy. Read it!” He tossed a crumpled letter
across to me.
"""
        ),
    ],
    align="justify",
    indent=20,
)


if __name__ == "__main__":
    main()
