from pdfje import Document, Page, Text


def test_hello(tmpdir):
    Document(
        [
            Page([Text("Hello", at=(200, 700)), Text("World", at=(300, 670))]),
            Page(),
            Page([Text("This is the last page!", at=(300, 600))]),
        ]
    ).to_path(tmpdir / "hello.pdf")
