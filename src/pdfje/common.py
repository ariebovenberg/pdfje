from dataclasses import fields
from itertools import chain
from typing import TypeVar

flatten = chain.from_iterable

Tclass = TypeVar("Tclass", bound=type)


# adapted from github.com/ericvsmith/dataclasses
# under its Apache 2.0 license.
def add_slots(cls: Tclass) -> Tclass:  # pragma: no cover
    if "__slots__" in cls.__dict__:
        raise TypeError(f"{cls.__name__} already specifies __slots__")

    cls_dict = dict(cls.__dict__)
    field_names = tuple(f.name for f in fields(cls))
    cls_dict["__slots__"] = field_names
    for field_name in field_names:
        # Remove our attributes, if present. They'll still be
        #  available in _MARKER.
        cls_dict.pop(field_name, None)
    # Remove __dict__ itself.
    cls_dict.pop("__dict__", None)
    # And finally create the class.
    qualname = getattr(cls, "__qualname__", None)
    cls = type(cls)(cls.__name__, cls.__bases__, cls_dict)
    if qualname is not None:
        cls.__qualname__ = qualname
    return cls
