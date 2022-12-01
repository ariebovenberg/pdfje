"""Low-level PDF objects and operations"""
import abc
import re
from binascii import hexlify
from dataclasses import dataclass
from functools import partial
from itertools import accumulate, chain, starmap
from typing import Collection, Iterable, Iterator, Sequence
from zlib import compress

from .common import add_slots

_HEADER = b"%PDF-1.7\n"
_FIRST_OFFSET = len(_HEADER)
OBJ_ID_XREF, OBJ_ID_CATALOG = 0, 1
ASCII = bytes
Byte = int  # 0-255


class Object(abc.ABC):
    __slots__ = ()

    @abc.abstractmethod
    def write(self) -> Iterable[bytes]:
        raise NotImplementedError()


ObjectID = int
"""ID of an object in the PDF file. Always >=0 and unique within a file."""

ObjectWithID = tuple[ObjectID, Object]


@add_slots
@dataclass(frozen=True)
class Bool(Object):
    value: bool

    def write(self) -> Iterable[bytes]:
        raise NotImplementedError()


@add_slots
@dataclass(frozen=True)
class Name(Object):
    value: ASCII

    def write(self) -> Iterable[bytes]:
        yield b"/"
        yield self.value


def _sanitize_name_char(c: Byte) -> bytes:
    # PDF32000-1:2008 (7.3.5) says ASCII from 33-126 is OK, except "#" (0x23)
    # which is the escape character.
    if c == 0x23:
        return b"#23"
    elif 33 <= c <= 126:
        return c.to_bytes(1, "big")
    # We decide to keep spaces, but remove the rest
    elif c == 0x20:
        return b"#20"
    else:
        return b""


def sanitize_name(s: bytes) -> bytes:
    return b"".join(map(_sanitize_name_char, s))


@add_slots
@dataclass(frozen=True)
class Int(Object):
    value: int

    def write(self) -> Iterable[bytes]:
        yield b"%i" % self.value


@add_slots
@dataclass(frozen=True)
class Float(Object):
    value: float

    def write(self) -> Iterable[bytes]:
        # NOTE: check if there's any Python-specific oddities with float repr
        # NOTE: exponential notation is not supported, only decimal
        # assert math.isfinite(self.value), "NaN and Inf not supported"
        raise NotImplementedError()


_STRING_ESCAPES = {
    b"\\": b"\\\\",
    b"\n": b"\\n",
    b"\r": b"\\r",
    b"\t": b"\\t",
    b"\b": b"\\b",
    b"\f": b"\\f",
    b"(": b"\\(",
    b")": b"\\)",
}


def _replace_with_escape(m: re.Match) -> bytes:
    return _STRING_ESCAPES[m.group()]


escape_string = partial(
    re.compile(b"(%b)" % b"|".join(map(re.escape, _STRING_ESCAPES))).sub,
    _replace_with_escape,
)


@add_slots
@dataclass(frozen=True)
class LiteralString(Object):
    value: bytes

    def write(self) -> Iterable[bytes]:
        yield b"("
        yield escape_string(self.value)
        yield b")"


@add_slots
@dataclass(frozen=True)
class HexString(Object):
    value: bytes

    def write(self) -> Iterable[bytes]:
        yield b"<"
        yield hexlify(self.value)
        yield b">"


@add_slots
@dataclass(frozen=True)
class Array(Object):
    items: Iterable[Object]

    def write(self) -> Iterable[bytes]:
        yield b"["
        for i in self.items:
            yield from i.write()
            yield b" "
        yield b"]"


@add_slots
@dataclass(frozen=True, init=False)
class Dictionary(Object):
    content: Collection[tuple[ASCII, Object]]

    def __init__(self, *content: tuple[ASCII, Object]) -> None:
        object.__setattr__(self, "content", content)

    def write(self) -> Iterable[bytes]:
        yield from _write_dict(self.content)


def _write_dict(d: Iterable[tuple[ASCII, Object]]) -> Iterable[bytes]:
    yield b"<<\n"
    for key, value in d:
        yield b"/"
        yield key
        yield b" "
        yield from value.write()
        yield b"\n"
    yield b">>"


@add_slots
@dataclass(frozen=True)
class Stream(Object):
    content: bytes
    meta: Collection[tuple[ASCII, Object]] = ()

    def write(self) -> Iterable[bytes]:
        content = compress(self.content)
        yield from _write_dict(
            chain(
                self.meta,
                [(b"Length", Int(len(content)))],
                [(b"Filter", Name(b"FlateDecode"))],
            )
        )
        yield b"\nstream\n"
        yield content
        yield b"\nendstream"


@add_slots
@dataclass(frozen=True)
class Ref(Object):
    target: ObjectID

    def write(self) -> Iterable[bytes]:
        yield b"%i 0 R" % self.target


def _write_obj(i: ObjectID, o: Object) -> Iterable[bytes]:
    yield b"%i 0 obj\n" % i
    yield from o.write()
    yield b"\nendobj\n"


def _write_trailer(
    offsets: Sequence[int], xref_offset: int
) -> Iterable[bytes]:
    yield b"xref\n%i %i\n0000000000 65535 f \n" % (
        OBJ_ID_XREF,
        len(offsets) + 1,
    )
    yield from map(b"%010i 00000 n \n".__mod__, offsets)
    yield b"trailer\n"
    yield from Dictionary(
        (b"Root", Ref(OBJ_ID_CATALOG)),
        (b"Size", Int(len(offsets) + 1)),
    ).write()
    yield b"\nstartxref\n%i\n%%%%EOF\n" % xref_offset


def write(objs: Iterable[ObjectWithID], /) -> Iterator[bytes]:
    yield _HEADER
    offsets = [_FIRST_OFFSET]
    for chunk in map(b"".join, starmap(_write_obj, objs)):
        offsets.append(len(chunk))
        yield chunk

    *offsets, xref_offset = accumulate(offsets)
    yield from _write_trailer(offsets, xref_offset)
