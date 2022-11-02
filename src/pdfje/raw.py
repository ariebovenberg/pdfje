"""Low-level PDF objects and operations"""
import abc
import math
import string
from dataclasses import dataclass
from itertools import accumulate, starmap
from typing import Iterable, Mapping, Sequence, Tuple

ALLOWED_NAME_CHARS = string.ascii_letters + "-_*?$" + string.digits
MAX_INT = 2_147_483_647
CHARS_REQUIRING_ESCAPE = "\n\t\r\f\b\\()"
HEADER = b"%PDF-1.3\n%\xc2\xa5\xc2\xb1\xc3\xab\n"
FIRST_OFFSET = len(HEADER)
OBJ_ID_XREF = 0
OBJ_ID_CATALOG = 1
FIRST_XREF_ENTRY = b"0000000000 65535 f\n"


class Object(abc.ABC):
    @abc.abstractmethod
    def write(self) -> bytes:
        ...


ObjectID = int
"""ID of an object in the PDF file. Always >=0"""


@dataclass(frozen=True)
class Bool(Object):
    value: bool

    def write(self) -> bytes:
        return b"true" if self.value else b"false"


@dataclass(frozen=True)
class Name(Object):
    value: str

    def __post_init__(self) -> None:
        assert all(
            map(ALLOWED_NAME_CHARS.__contains__, self.value)
        ), "only simple alphanumeric names for now"

    def write(self) -> bytes:
        return f"/{self.value}".encode()


@dataclass(frozen=True)
class Int(Object):
    value: int

    def __post_init__(self) -> None:
        # TODO: check if this is a real limitation
        assert MAX_INT > self.value > -MAX_INT, "this int is too large"

    def write(self) -> bytes:
        return str(self.value).encode()


@dataclass(frozen=True)
class Float(Object):
    value: float

    def __post_init__(self) -> None:
        assert math.isfinite(self.value), "NaN and Inf not supported"

    def write(self) -> bytes:
        # TODO: check if there's any Python-specific oddities with float repr
        return str(self.value).encode()


@dataclass(frozen=True)
class String(Object):
    value: str

    def write(self) -> bytes:
        assert not any(
            map(self.value.__contains__, CHARS_REQUIRING_ESCAPE)
        ), "parentheses and nonprintable newlines/tabs currently not supported"
        return f"({self.value})".encode()


@dataclass(frozen=True)
class Array(Object):
    items: Tuple[Object, ...]

    def write(self) -> bytes:
        return b"[%s]" % b" ".join(i.write() for i in self.items)


@dataclass(frozen=True)
class Dictionary(Object):
    content: Mapping[str, Object]

    def __post_init__(self) -> None:
        assert len(self.content) <= 4096, "PDF dictionary too large"

    def write(self) -> bytes:
        return _write_dict(self.content)


def _write_dict(d: Mapping[str, Object]) -> bytes:
    return b"<<%s>>" % b" ".join(
        b"/%s %s" % (k.encode(), v.write()) for k, v in d.items()
    )


@dataclass(frozen=True)
class Stream(Object):
    meta: Mapping[str, Object]
    content: bytes

    def __post_init__(self) -> None:
        assert len(self.meta) <= 4096, "PDF dictionary too large"

    def write(self) -> bytes:
        return _write_dict(self.meta) + b"\nstream\n%sendstream" % self.content


@dataclass(frozen=True)
class Ref(Object):
    target: ObjectID

    def write(self) -> bytes:
        return b"%i 0 R" % self.target


def _write_obj(i: ObjectID, o: Object) -> bytes:
    return b"%i 0 obj\n%s\nendobj\n" % (i, o.write())


def write(objs: Iterable[tuple[ObjectID, Object]], /) -> bytes:
    return b"".join(write_iter(objs))


def _write_trailer(
    obj_offsets: Sequence[int], xref_offset: int
) -> Iterable[bytes]:
    yield b"xref\n%i %i\n" % (OBJ_ID_XREF, len(obj_offsets) + 1)
    yield FIRST_XREF_ENTRY
    for offset in obj_offsets:
        yield b"%010i 00000 n\n" % offset
    yield b"trailer\n"
    yield Dictionary(
        {
            "Root": Ref(OBJ_ID_CATALOG),
            "Size": Int(len(obj_offsets)),
        }
    ).write()
    yield b"\nstartxref\n%i\n%%%%EOF" % (xref_offset)


def write_iter(objs: Iterable[tuple[ObjectID, Object]], /) -> Iterable[bytes]:
    yield HEADER
    offsets = [FIRST_OFFSET]
    for chunk in starmap(_write_obj, objs):
        offsets.append(len(chunk))
        yield chunk

    *obj_offsets, xref_offset = accumulate(offsets)
    yield from _write_trailer(obj_offsets, xref_offset)
