from pdfje import Document


def test_empty(tmpdir):
    doc = Document()
    doc.to_path(tmpdir / "empty.pdf")
