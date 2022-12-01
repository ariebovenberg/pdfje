from __future__ import annotations

import abc
import enum
from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO
from itertools import chain, count, starmap
from pathlib import Path
from typing import AbstractSet, Collection, Iterable, Mapping

import fontTools.subset
from fontTools.ttLib import TTFont as FontToolsTTF

from . import atoms
from .atoms import ASCII, sanitize_name
from .common import add_slots

FontID = bytes  # unique name assigned to a font within a PDF

_CodePoint = int  # a unicode code point
_GlyphName = str  # name uniquely identifying a glyph in a TTF font
_GlyphID = int  # integer unique identifying a glyph in a TTF font
_Char = str  # 1-length string, i.e. a unicode character
_OBJS_PER_EMBEDDED_FONT = 7
_CID = int  # 16-bit ID uniquely identifying a character in a PDF
_CID_MAX = 0xFFFF  # character IDs are stored as 16-bit values
_TEXTSPACE_TO_GLYPHSPACE = 1000  # See PDF32000-1:2008 (9.7.3)
_CIDSYS_INFO = atoms.Dictionary(
    (b"Registry", atoms.LiteralString(b"Adobe")),
    (b"Ordering", atoms.LiteralString(b"UCS")),
    (b"Supplement", atoms.Int(0)),
)
_EMPTY_ITERATOR = iter(())
_SUBSET_OPTIONS = fontTools.subset.Options(
    drop_tables=[
        "BASE",
        "JSTF",
        "DSIG",
        "EBDT",
        "EBLC",
        "EBSC",
        "PCLT",
        "LTSH",
        "Feat",
        "Glat",
        "Gloc",
        "Silf",
        "Sill",
        "GDEF",
        "GSUB",
        "GPOS",
        "MATH",
        "hdmx",
    ],
    notdef_outline=True,
    recommended_glyphs=True,
)


# See PDF 32000-1:2008, section 9.8.2
class FontDescriptorFlag(enum.IntFlag):
    FIXED_PITCH = 1 << 0
    SERIF = 1 << 1
    SYMBOLIC = 1 << 2
    SCRIPT = 1 << 3
    NONSYMBOLIC = 1 << 5
    ITALIC = 1 << 6
    ALL_CAP = 1 << 16
    SMALL_CAP = 1 << 17
    FORCE_BOLD = 1 << 18


class Font(abc.ABC):
    "Base class for builtin and embedded fonts"
    __slots__ = ()

    @staticmethod
    def from_path(p: Path) -> "TTF":
        return TTF(p)


@add_slots
@dataclass(frozen=True)
class TTF(Font):
    path: Path


@add_slots
@dataclass(frozen=True, repr=False)
class Builtin(Font):
    name: ASCII

    def __repr__(self) -> str:
        cls = type(self)
        return f"{cls.__module__}.{cls.__name__}({self.name.decode()})"


class IncludedFont(abc.ABC):
    """A font with extra information on how to include it in the document"""

    __slots__ = ()

    font: Font
    id: FontID

    @abc.abstractmethod
    def to_resource(self) -> atoms.Object:
        raise NotImplementedError()

    @abc.abstractmethod
    def to_atoms(self) -> Iterable[atoms.ObjectWithID]:
        raise NotImplementedError()

    @abc.abstractmethod
    def encode(self, s: str) -> bytes:
        raise NotImplementedError()


@add_slots
@dataclass(frozen=True)
class BuiltinUse(IncludedFont):
    font: Builtin
    id: FontID

    def to_resource(self) -> atoms.Object:
        return atoms.Dictionary(
            (b"Type", atoms.Name(b"Font")),
            (b"Subtype", atoms.Name(b"Type1")),
            (b"BaseFont", atoms.Name(self.font.name)),
            (b"Encoding", atoms.Name(b"WinAnsiEncoding")),
        )

    def to_atoms(self) -> Iterable[atoms.ObjectWithID]:
        return _EMPTY_ITERATOR

    @staticmethod
    def encode(s: str) -> bytes:
        return s.encode("cp1252", errors="replace")


@add_slots
@dataclass(frozen=True)
class EmbeddedSubset(IncludedFont):
    id: FontID
    obj_id: atoms.ObjectID
    font: TTF
    ttf: FontToolsTTF

    # NOTE: both mappings are ordered the same
    cids: Mapping[_CodePoint, _CID]
    glyphs: Mapping[_CodePoint, _GlyphID]

    @staticmethod
    def from_chars(
        id: FontID,
        obj_id: atoms.ObjectID,
        font: TTF,
        chars: AbstractSet[_Char],
    ) -> EmbeddedSubset:
        ttf = FontToolsTTF(font.path)
        sub = fontTools.subset.Subsetter(_SUBSET_OPTIONS)
        # It's important for the CID/GID and unicode map that
        # \U0000 is included
        sub.populate(unicodes=chain(map(ord, chars), (0,)))
        sub.subset(ttf)
        cmap: dict[_CodePoint, _GlyphName] | None = ttf.getBestCmap()
        assert cmap is not None, "Couldn't read font from file"
        # PDF only supports 16-bit character/glyph entries,
        # thus there is a theoretical limit to the number of unique characters
        # in a document per font. There are workarounds, but most fonts don't
        # even have this many glyphs and this many different characters
        # seem unlikely to occur in common text. Thus, we just assert.
        assert len(chars) < _CID_MAX
        gname_to_gid: dict[_GlyphName, _GlyphID] = ttf.getReverseGlyphMap()
        return EmbeddedSubset(
            id,
            obj_id,
            font,
            ttf,
            dict(zip(cmap, count())),
            dict(zip(cmap, map(gname_to_gid.__getitem__, cmap.values()))),
        )

    def encode(self, s: str) -> bytes:
        return s.translate(self.cids).encode(
            "utf-16be", errors="surrogatepass"
        )

    def to_resource(self) -> atoms.Object:
        return atoms.Ref(self.obj_id)

    def to_atoms(self) -> Iterable[atoms.ObjectWithID]:
        scale = _TEXTSPACE_TO_GLYPHSPACE / self.ttf["head"].unitsPerEm
        # According to PDF32000-1:2008 (9.6.4) font subsets
        # need to begin with an arbitrary six-letter tag.
        # The tag should be the same per font subset added by a PDF writer.
        # We choose `PDFJE` padded with an `A` at the front.
        tagged_name = atoms.Name(
            b"APDFJE+"
            + sanitize_name(self.ttf["name"].getBestFullName().encode())
        )

        (
            descendant_id,
            unicodemap_id,
            cidsysinfo_id,
            descriptor_id,
            cid_gid_map_id,
            file_id,
        ) = range(self.obj_id + 1, self.obj_id + _OBJS_PER_EMBEDDED_FONT)
        # These objects are based on PDF32000-1:2008, page 293
        yield (
            self.obj_id,
            atoms.Dictionary(
                (b"Type", atoms.Name(b"Font")),
                (b"Subtype", atoms.Name(b"Type0")),
                (b"BaseFont", tagged_name),
                (b"Encoding", atoms.Name(b"Identity-H")),
                (
                    b"DescendantFonts",
                    atoms.Array((atoms.Ref(descendant_id),)),
                ),
                (b"ToUnicode", atoms.Ref(unicodemap_id)),
            ),
        )
        yield (
            descendant_id,
            atoms.Dictionary(
                (b"Type", atoms.Name(b"Font")),
                (b"Subtype", atoms.Name(b"CIDFontType2")),
                (b"BaseFont", tagged_name),
                (b"CIDSystemInfo", atoms.Ref(cidsysinfo_id)),
                (b"FontDescriptor", atoms.Ref(descriptor_id)),
                (
                    b"DW",
                    atoms.Int(
                        round(scale * self.ttf["hmtx"].metrics[".notdef"][0])
                    ),
                ),
                (b"W", _encode_widths(self.ttf, scale)),
                (b"CIDToGIDMap", atoms.Ref(cid_gid_map_id)),
            ),
        )
        yield (unicodemap_id, _to_unicode_map(self.cids.items()))
        yield (cidsysinfo_id, _CIDSYS_INFO)
        yield (
            descriptor_id,
            atoms.Dictionary(
                (b"Type", atoms.Name(b"FontDescriptor")),
                (b"FontName", tagged_name),
                (b"Flags", _encode_flags(self.ttf)),
                (b"FontBBox", _encode_bbox(self.ttf, scale)),
                (
                    b"ItalicAngle",
                    atoms.Int(round(self.ttf["post"].italicAngle)),
                ),
                (
                    b"Ascent",
                    atoms.Int(round(self.ttf["hhea"].ascent * scale)),
                ),
                (
                    b"Descent",
                    atoms.Int(round(self.ttf["hhea"].descent * scale)),
                ),
                (b"CapHeight", _encode_cap_height(self.ttf, scale)),
                (b"StemV", _encode_stem_v(self.ttf)),
                (b"FontFile2", atoms.Ref(file_id)),
            ),
        )
        yield (cid_gid_map_id, _encode_cid_gid_map(self.cids, self.glyphs))
        yield (file_id, _encode_ttf_with_side_effects(self.ttf))


def _encode_bbox(f: FontToolsTTF, scale: float) -> atoms.Array:
    head = f["head"]
    return atoms.Array(
        atoms.Int(round(v * scale))
        for v in (head.xMin, head.yMin, head.xMax, head.yMax)
    )


def _encode_flags(f: FontToolsTTF) -> atoms.Int:
    return atoms.Int(
        FontDescriptorFlag.SYMBOLIC
        | (f["post"].isFixedPitch and FontDescriptorFlag.FIXED_PITCH)
        | (bool(f["post"].italicAngle) and FontDescriptorFlag.ITALIC)
        | (f["OS/2"].usWeightClass >= 600 and FontDescriptorFlag.FORCE_BOLD)
    )


# WARNING: the act of saving fontTools' TTFont leads to changed properties
# such as ttfont['head'].xMin. Beware of when you call this function!
def _encode_ttf_with_side_effects(f: FontToolsTTF) -> atoms.Stream:
    tmp = BytesIO()
    f.save(tmp)
    content = tmp.getvalue()
    return atoms.Stream(content, ((b"Length1", atoms.Int(len(content))),))


def _encode_cid_gid_map(
    cids: Iterable[_CodePoint],  # ordered by CID (ascending)
    glyphs: Mapping[_CodePoint, _GlyphID],
) -> atoms.Object:
    # See PDF32000-1:2008 (table 117) for instructions on how to encode this
    return atoms.Stream(b"".join(glyphs[c].to_bytes(2, "big") for c in cids))


def _encode_widths(f: FontToolsTTF, scale: float) -> atoms.Array:
    # See PDF32000-1:2008 (9.7.4.3) for how character widths are encoded.
    # For now we choose to simply encode all widths sequentially.
    # It should be made more efficient in the future,
    # especially for fixed width fonts.
    return atoms.Array(
        (
            atoms.Int(0),
            atoms.Array(
                atoms.Int(round(scale * f["hmtx"].metrics[g][0]))
                for g in f.getBestCmap().values()
            ),
        )
    )


def _encode_cap_height(f: FontToolsTTF, scale: float) -> atoms.Int:
    # Apparently not all TTF fonts properly have the capheight accessible.
    # We can fall back to the ascender height, which is usually slightly lower.
    try:
        v = f["OS/2"].sCapHeight
    except AttributeError:
        v = f["hhea"].ascent

    return atoms.Int(round(v * scale))


_FONTWEIGHT_TO_STEM_V_RATIO = (241 - 50) / (900 - 100)


def _encode_stem_v(f: FontToolsTTF) -> atoms.Int:
    # See stackoverflow.com/questions/35485179.
    # The StemV value cannot be directly retrieved from TTF type fonts.
    # Common wisdom seems to be to map the font weight (100-900) to reasonable
    # StemV values (50-241).
    return atoms.Int(
        round(50 + _FONTWEIGHT_TO_STEM_V_RATIO * f["OS/2"].usWeightClass)
    )


def _to_unicode_map(m: Collection[tuple[_CodePoint, _CID]]) -> atoms.Object:
    # The 'To Unicode' map ensures that the correct characters are copied
    # from a text selection.
    return atoms.Stream(
        _TO_UNICODE_CMAP
        % (
            b"".join(_CIDSYS_INFO.write()),
            len(m),
            b"\n".join(
                b"<%04X> <%b>" % (cid, utf16be_hex(code)) for code, cid in m
            ),
        )
    )


def utf16be_hex(c: _CodePoint) -> bytes:
    if c <= 0xFFFF:
        return b"%04X" % c
    else:
        return b"%04X%04X" % (
            (c - 0x10000) >> 10 | 0xD800,
            (c & 0x3FF) | 0xDC00,
        )


def usage(
    text: Iterable[tuple[str, Font]], first_id: atoms.ObjectID
) -> Iterable[IncludedFont]:
    next_name = map(b"F%i".__mod__, count()).__next__
    next_id = count(first_id, _OBJS_PER_EMBEDDED_FONT).__next__
    embeds: defaultdict[
        TTF, tuple[FontID, atoms.ObjectID, set[_Char]]
    ] = defaultdict(lambda: (next_name(), next_id(), set()))
    builtins: defaultdict[Builtin, FontID] = defaultdict(next_name)

    for content, font in text:
        if isinstance(font, Builtin):
            builtins[font]
        else:
            assert isinstance(font, TTF)
            embeds[font][2].update(content)

    return chain(
        starmap(BuiltinUse, builtins.items()),
        (
            EmbeddedSubset.from_chars(name, id, font, chars)
            for font, (name, id, chars) in embeds.items()
        ),
    )


# based on PDF32000-1:2008, page 294
_TO_UNICODE_CMAP = b"""\
/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CIDSystemInfo
%b def
/CMapName /Adobe-Identity-UCS def
/CMapType 2 def
1 begincodespacerange
<0000> <FFFF>
endcodespacerange
%i beginbfchar
%b
endbfchar
endcmap
CMapName currentdict /CMap defineresource pop
end
end"""
