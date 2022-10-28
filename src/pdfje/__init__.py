import os
from pathlib import Path

__all__ = ["Document"]


class Document:
    def to_path(self, pathlike: os.PathLike, /) -> None:
        path = Path(pathlike)
        path.write_bytes(_EMPTY_PDF)


_EMPTY_PDF = b"""\
%PDF-1.3
1 0 obj<</Pages 2 0 R>>endobj
2 0 obj<</Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Parent 2 0 R>>endobj
trailer <</Root 1 0 R>>\
"""
