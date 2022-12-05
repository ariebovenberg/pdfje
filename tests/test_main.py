from pathlib import Path as FilePath

from pdfje import (
    Document,
    Font,
    Page,
    Rule,
    Style,
    Text,
    courier,
    helvetica,
    times_roman,
)

HERE = FilePath(__file__).parent

ZALGO = "t̶͈̓̕h̴̩̖͋̈́e̷̛̹ ̴̠͎̋̀p̷̦̔o̴̘͔̓n̸̞̙̐̕y̷̙̠̍ ̶̱̞̃h̶͈̮̅̆ë̸͍̟́̓ ̷̳̜̂c̵̢̡͋o̸̰̫͗̽m̷̨̿̕e̶̛̗̲͆s̸̨̭̐"  # noqa


class TestWrite:
    def test_no_arguments(self):
        output = Document().write()
        assert isinstance(next(output), bytes)
        assert b"".join(output).endswith(b"%%EOF\n")

    def test_string(self, tmpdir):
        loc = str(tmpdir / "foo.pdf")
        Document().write(loc)
        assert FilePath(loc).read_bytes().endswith(b"%%EOF\n")

    def test_path(self, tmpdir):
        loc = FilePath(tmpdir / "foo.pdf")
        Document().write(loc)
        assert loc.read_bytes().endswith(b"%%EOF\n")

    def test_fileobj(self, tmpdir):
        loc = FilePath(tmpdir / "foo.pdf")
        with loc.open(mode="wb") as f:
            Document().write(f)
        assert loc.read_bytes().endswith(b"%%EOF\n")


def test_empty(outfile):
    Document().write(outfile)


def test_one_string(outfile):
    Document(LOREM_IPSUM).write(outfile)


def test_pages(outfile):
    Document(
        [
            Page("First!"),
            Page(ZEN_OF_PYTHON),
            Page(
                [
                    "here is",
                    Rule(),
                    Text("BIG", Style(fontsize=40)),
                    "text",
                    Rule(),
                ]
            ),
        ]
    ).write(outfile)


def test_rotate(outfile):
    Document(
        [
            Page(f"rotated {angle}", rotate=angle)  # type: ignore
            for angle in (0, 90, 180, 270)
        ]
    ).write(outfile)


def test_page_textfill(outfile):
    Document([Page(LOREM_IPSUM)]).write(outfile)


def test_fonts(outfile):
    dejavu = Font.from_path(HERE / "resources/DejaVuSansCondensed.ttf")
    roboto = Font.from_path(HERE / "resources/Roboto.ttf")
    Document(
        [
            Page(
                [
                    Text("Cheers, Cour®ier", courier),
                    Text("Hey hélvetica!", helvetica),
                    Text("Hí RobotὍ... ", roboto),
                    Text("Hello 𝌷 agaîn,\nDejaVü!", dejavu),
                    Text("Good †imes", times_roman),
                    Text("(check that the text above can be copied!)"),
                    Text("unknown char (builtin font): ∫"),
                    Text("unknown char (embedded font): ⟤", dejavu),
                    Text(f"zalgo: {ZALGO}", dejavu),
                    Text("zero byte: \x00", dejavu),
                ]
            )
        ]
    ).write(outfile)


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
Mauris at odio nec sem volutpat aliquam. Aliquam erat volutpat.

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
Duis pellentesque dui et ipsum suscipit, in semper odio dictum.

Sed in fermentum leo. Donec maximus suscipit metus. \
Nulla convallis tortor mollis urna maximus mattis. \
Sed aliquet leo ac sem aliquam, et ultricies mauris maximus. \
Cras orci ex, fermentum nec purus non, molestie venenatis odio. \
Etiam vitae sollicitudin nisl. Sed a ullamcorper velit.

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
Nullam volutpat sapien quis tincidunt sagittis.
"""

ZEN_OF_PYTHON = """\
Beautiful is better than ugly.
Explicit is better than implicit.
Simple is better than complex.
Complex is better than complicated.
Flat is better than nested.
Sparse is better than dense.
Readability counts.
Special cases aren't special enough to break the rules.
Although practicality beats purity.
Errors should never pass silently.
Unless explicitly silenced.
In the face of ambiguity, refuse the temptation to guess.
There should be one-- and preferably only one --obvious way to do it.
Although that way may not be obvious at first unless you're Dutch.
Now is better than never.
Although never is often better than *right* now.
If the implementation is hard to explain, it's a bad idea.
If the implementation is easy to explain, it may be a good idea.
Namespaces are one honking great idea -- let's do more of those!
"""
