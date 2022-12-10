from pdfje import (
    A3,
    A4,
    A6,
    AutoPage,
    Column,
    Document,
    Page,
    Paragraph,
    Style,
    inch,
    italic,
    mm,
    times_roman,
)


def main() -> None:
    "Generate a PDF with differently styled text layed out in various columns"
    Document(
        [
            AutoPage(
                # Repeat the same text in different styles
                [Paragraph(LOREM_IPSUM, s) for s in STYLES * 3],
                # Cycle through the three page templates
                template=lambda i: TEMPLATES[i % 3],
            )
        ]
    ).write("multicolumn.pdf")


STYLES = [Style(size=10), "#225588" | italic, Style(size=15, font=times_roman)]
TEMPLATES = [
    # A one-column page
    Page(size=A6, margin=mm(15)),
    # A two-column page
    Page(
        columns=[
            Column(
                (inch(1), inch(1)),
                width=(A4.x / 2) - inch(1.25),
                height=A4.y - inch(2),
            ),
            Column(
                (A4.x / 2 + inch(0.25), inch(1)),
                width=(A4.x / 2) - inch(1.25),
                height=A4.y - inch(2),
            ),
        ]
    ),
    # A page with three arbitrary columns
    Page(
        size=A3.flip(),
        columns=[
            Column(
                (inch(1), inch(1)),
                width=(A3.y / 4),
                height=A3.x - inch(2),
            ),
            Column(
                (A3.y / 4 + inch(1.5), inch(5)),
                width=(A3.y / 2) - inch(1.25),
                height=A3.x - inch(8),
            ),
            Column(
                ((A3.y * 0.8) + inch(0.25), inch(4)),
                width=(A3.y / 10),
                height=inch(5),
            ),
        ],
    ),
]


LOREM_IPSUM = """\
Lorem ipsum dolor sit amet, consectetur adipiscing elit. \
Integer sed aliquet justo. Donec eu ultricies velit, porta pharetra massa. \
Ut non augue a urna iaculis vulputate ut sit amet sem. \
Nullam lectus felis, rhoncus sed convallis a, egestas semper risus. \
Fusce gravida metus non vulputate vestibulum. \
Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere \
cubilia curae; Donec placerat suscipit velit. \
Mauris tincidunt lorem a eros eleifend tincidunt. \
Maecenas faucibus imperdiet massa quis pretium. Integer in lobortis nisi. \
Mauris at odio nec sem volutpat aliquam. Aliquam erat volutpat. \

Fusce at vehicula justo. Vestibulum eget viverra velit. \
Vivamus et nisi pulvinar, elementum lorem nec, volutpat leo. \
Aliquam erat volutpat. Sed tristique quis arcu vitae vehicula. \
Morbi egestas vel diam eget dapibus. Donec sit amet lorem turpis. \
Maecenas ultrices nunc vitae enim scelerisque tempus. \
Maecenas aliquet dui non hendrerit viverra. \
Aliquam fringilla, est sit amet gravida convallis, elit ipsum efficitur orci, \
eget convallis neque nunc nec lorem. Nam nisl sem, \
tristique a ultrices sed, finibus id enim.

Etiam vel dolor ultricies, gravida felis in, vestibulum magna. \
In diam ex, elementum ut massa a, facilisis sollicitudin lacus. \
Integer lacus ante, ullamcorper ac mauris eget, rutrum facilisis velit. \
Mauris eu enim efficitur, malesuada ipsum nec, sodales enim. \
Nam ac tortor velit. Suspendisse ut leo a felis aliquam dapibus ut a justo. \
Vestibulum sed commodo tortor. Sed vitae enim ipsum. \
Duis pellentesque dui et ipsum suscipit, in semper odio dictum. \

Sed in fermentum leo. Donec maximus suscipit metus. \
Nulla convallis tortor mollis urna maximus mattis. \
Sed aliquet leo ac sem aliquam, et ultricies mauris maximus. \
Cras orci ex, fermentum nec purus non, molestie venenatis odio. \
Etiam vitae sollicitudin nisl. Sed a ullamcorper velit. \

Aliquam congue aliquet eros scelerisque hendrerit. Vestibulum quis ante ex. \
Fusce venenatis mauris dolor, nec mattis libero pharetra feugiat. \
Pellentesque habitant morbi tristique senectus et netus et malesuada \
fames ac turpis egestas. Cras vitae nisl molestie augue finibus lobortis. \
In hac habitasse platea dictumst. Maecenas rutrum interdum urna, \
ut finibus tortor facilisis ac. Donec in fringilla mi. \
Sed molestie accumsan nisi at mattis. \
Integer eget orci nec urna finibus porta. \
Sed eu dui vel lacus pulvinar blandit sed a urna. \
Quisque lacus arcu, mattis vel rhoncus hendrerit, dapibus sed massa. \
Vivamus sed massa est. In hac habitasse platea dictumst. \
Nullam volutpat sapien quis tincidunt sagittis. \
"""

if __name__ == "__main__":
    main()
