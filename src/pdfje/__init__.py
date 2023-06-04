from __future__ import annotations

from .common import RGB, XY, black, blue, cyan, lime, magenta, red, yellow
from .document import Document
from .layout.pages import AutoPage
from .page import Column, Page

__version__ = __import__("importlib.metadata").metadata.version(__name__)

__all__ = [
    # document & pages
    "Document",
    "Page",
    "Column",
    "AutoPage",
    # helpers
    "red",
    "lime",
    "blue",
    "black",
    "yellow",
    "magenta",
    "cyan",
    # common
    "RGB",
    "XY",
]
