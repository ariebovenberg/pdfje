from .common import RGB, XY, black, blue, cyan, lime, magenta, red, yellow
from .document import AutoPage, Document, Page

__version__ = __import__("importlib.metadata").metadata.version(__name__)

__all__ = [
    # document & pages
    "Document",
    "Page",
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
