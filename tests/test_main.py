from pathlib import Path

from pdfje import Document, Font, Page, Text, courier, helvetica, times_roman

HERE = Path(__file__).parent

ZALGO = "t̶͈̓̕h̴̩̖͋̈́e̷̛̹ ̴̠͎̋̀p̷̦̔o̴̘͔̓n̸̞̙̐̕y̷̙̠̍ ̶̱̞̃h̶͈̮̅̆ë̸͍̟́̓ ̷̳̜̂c̵̢̡͋o̸̰̫͗̽m̷̨̿̕e̶̛̗̲͆s̸̨̭̐"  # noqa


class TestWrite:
    def test_no_arguments(self):
        output = Document().write()
        assert isinstance(next(output), bytes)
        assert b"".join(output).endswith(b"%%EOF\n")

    def test_string(self, tmpdir):
        loc = str(tmpdir / "foo.pdf")
        Document().write(loc)
        assert Path(loc).read_bytes().endswith(b"%%EOF\n")

    def test_path(self, tmpdir):
        loc = Path(tmpdir / "foo.pdf")
        Document().write(loc)
        assert loc.read_bytes().endswith(b"%%EOF\n")

    def test_fileobj(self, tmpdir):
        loc = Path(tmpdir / "foo.pdf")
        with loc.open(mode="wb") as f:
            Document().write(f)
        assert loc.read_bytes().endswith(b"%%EOF\n")


def test_empty(outfile):
    Document().write(outfile)


def test_string(outfile):
    Document("Olá Mundo!\nHello World!\n\r\nGoodbye.").write(outfile)


def test_pages(outfile):
    Document(
        [
            Page("First!"),
            Page(
                """\
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
            ),
            Page(["here is", Text("BIG", size=40), "text"]),
        ]
    ).write(outfile)


def test_rotate(outfile):
    Document(
        [
            Page(f"rotated {angle}", rotate=angle)  # type: ignore
            for angle in (0, 90, 180, 270)
        ]
    ).write(outfile)


def test_fonts(outfile):
    dejavu = Font.from_path(HERE / "resources/DejaVuSansCondensed.ttf")
    roboto = Font.from_path(HERE / "resources/Roboto.ttf")
    Document(
        [
            Page(
                [
                    Text("Cheers, Cour®ier", font=courier),
                    Text("Hey hélvetica!", font=helvetica),
                    Text("Hí RobotὍ... ", font=roboto),
                    Text("Hello 𝌷 agaîn,\nDejaVü!", font=dejavu),
                    Text("Good †imes", font=times_roman),
                    Text("(check that the text above can be copied!)"),
                    Text("unknown char (builtin font): ∫"),
                    Text("unknown char (embedded font): ⟤", font=dejavu),
                    Text(f"zalgo: {ZALGO}", font=dejavu),
                    Text("zero byte: \x00", font=dejavu),
                ]
            )
        ]
    ).write(outfile)
