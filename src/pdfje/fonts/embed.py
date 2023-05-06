from __future__ import annotations

import enum
from collections import defaultdict
from dataclasses import dataclass, field
from io import BytesIO
from itertools import count
from operator import methodcaller
from pathlib import Path
from typing import TYPE_CHECKING, Collection, Iterable

from .. import atoms
from ..atoms import sanitize_name
from ..common import (
    Char,
    Func,
    Ordinal,
    Pt,
    add_slots,
    dictget,
    first,
    pipe,
    setattr_frozen,
)
from .common import (
    TEXTSPACE_TO_GLYPHSPACE,
    Font,
    FontID,
    GlyphPt,
    KerningTable,
    kern,
)

try:
    import fontTools.subset
    from fontTools.ttLib import TTFont
except ModuleNotFoundError:  # pragma: no cover
    HAS_FONTTOOLS = False
else:
    HAS_FONTTOOLS = True
    from ..vendor import get_kerning_pairs


OBJS_PER_EMBEDDED_FONT = 7
_GlyphName = str  # name uniquely identifying a glyph in a TTF font
_CID = int  # CharacterID. 16-bit ID uniquely identifying a character in a PDF
_CID_MAX = 0xFFFF  # character IDs are stored as 16-bit values
_REPLACEMENT_GLYPH: _GlyphName = ".notdef"
_CIDSYS_INFO = atoms.Dictionary(
    (b"Registry", atoms.LiteralStr(b"Adobe")),
    (b"Ordering", atoms.LiteralStr(b"UCS")),
    (b"Supplement", atoms.Int(0)),
)


def _utf16be_hex(c: Ordinal) -> bytes:
    if c <= 0xFFFF:
        return b"%04X" % c
    else:
        return b"%04X%04X" % (
            (c - 0x10000) >> 10 | 0xD800,
            (c & 0x3FF) | 0xDC00,
        )


if TYPE_CHECKING or HAS_FONTTOOLS:
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

    @add_slots
    @dataclass(frozen=True, eq=False, repr=False)
    class Subset(Font):
        id: FontID
        ttf: TTFont
        charwidth: Func[Char, GlyphPt]
        cids: defaultdict[Ordinal, _CID]
        scale: float  # from glyph units to GlyphPt
        kerning: KerningTable | None
        spacewidth: GlyphPt = field(init=False)

        encoding_width = 2

        def __repr__(self) -> str:
            return (
                f"{type(self).__name__}({self.ttf['name'].getBestFullName()})"
            )

        def __post_init__(self) -> None:
            setattr_frozen(self, "spacewidth", self.charwidth(" "))

        @staticmethod
        def new(i: FontID, font: Path) -> Subset:
            ttf = TTFont(font)
            scale = TEXTSPACE_TO_GLYPHSPACE / ttf["head"].unitsPerEm
            return Subset(
                id=i,
                ttf=ttf,
                # FUTURE: cache calls to this function?
                charwidth=pipe(
                    ord,
                    dictget(ttf.getBestCmap(), _REPLACEMENT_GLYPH),
                    ttf["hmtx"].metrics.__getitem__,
                    first,
                    scale.__mul__,
                ),
                cids=defaultdict(count().__next__),
                scale=scale,
                kerning=(
                    pipe(dictget(kernpairs, 0), scale.__mul__)
                    if (kernpairs := get_kerning_pairs.for_font(ttf))
                    else None
                ),
            )

        def width(self, s: str) -> Pt:
            return sum(map(self.charwidth, s)) / TEXTSPACE_TO_GLYPHSPACE

        def encode(self, s: str) -> bytes:
            return (
                s.translate(self.cids)
                # Encoding by UTF-16BE is a fast way to convert from CIDs
                # to bytes. Because not all CIDs are valid codepoints,
                # we use surrogatepass.
                .encode("utf-16be", errors="surrogatepass")
            )

        def kern(
            self, s: str, /, prev: Char | None
        ) -> Iterable[tuple[int, GlyphPt]]:
            return kern(self.kerning, s, prev) if self.kerning else ()

        def charkern(self, a: Char, b: Char, /) -> GlyphPt:
            return self.kerning((a, b)) if self.kerning else 0

        def to_objects(self, obj_id: atoms.ObjectID) -> Iterable[atoms.Object]:
            # PDF only supports 16-bit character/glyph entries,
            # thus there is a theoretical limit to the number of unique
            # characters in a document per font. There are workarounds,
            # but most fonts don't even have this many glyphs and this many
            # different characters seem unlikely to occur in common text.
            # Thus, we just assert.
            assert len(self.cids) < _CID_MAX
            # According to PDF32000-1:2008 (9.6.4) font subsets
            # need to begin with an arbitrary six-letter tag.
            # The tag should be the same per font subset added by a PDF writer.
            # We choose `PDFJE` padded with an `A` at the front.
            tagged_name = atoms.Name(
                b"APDFJE+"
                # FUTURE: handle empty/duplicate name?
                + sanitize_name(self.ttf["name"].getBestFullName().encode())
            )
            sub = fontTools.subset.Subsetter(_SUBSET_OPTIONS)
            sub.populate(unicodes=self.cids)
            sub.subset(self.ttf)
            (
                descendant_id,
                unicodemap_id,
                cidsysinfo_id,
                descriptor_id,
                cid_gid_map_id,
                file_id,
            ) = range(obj_id + 1, obj_id + OBJS_PER_EMBEDDED_FONT)
            # These objects are based on PDF32000-1:2008, page 293
            yield (
                obj_id,
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
                        atoms.Real(
                            self.ttf["hmtx"][_REPLACEMENT_GLYPH][0]
                            * self.scale
                        ),
                    ),
                    (
                        b"W",
                        _encode_widths(
                            map(pipe(chr, self.charwidth), self.cids)
                        ),
                    ),
                    (b"CIDToGIDMap", atoms.Ref(cid_gid_map_id)),
                ),
            )
            yield (
                unicodemap_id,
                atoms.Stream(_unicode_map(self.cids.items())),
            )
            yield (cidsysinfo_id, _CIDSYS_INFO)
            yield (
                descriptor_id,
                atoms.Dictionary(
                    (b"Type", atoms.Name(b"FontDescriptor")),
                    (b"FontName", tagged_name),
                    (b"Flags", _encode_flags(self.ttf)),
                    (b"FontBBox", _encode_bbox(self.ttf, self.scale)),
                    (
                        b"ItalicAngle",
                        atoms.Int(round(self.ttf["post"].italicAngle)),
                    ),
                    (
                        b"Ascent",
                        atoms.Int(round(self.ttf["hhea"].ascent * self.scale)),
                    ),
                    (
                        b"Descent",
                        atoms.Int(
                            round(self.ttf["hhea"].descent * self.scale)
                        ),
                    ),
                    (b"CapHeight", _encode_cap_height(self.ttf, self.scale)),
                    (b"StemV", _encode_stem_v(self.ttf)),
                    (b"FontFile2", atoms.Ref(file_id)),
                ),
            )
            yield (cid_gid_map_id, _encode_cid_gid_map(self.ttf, self.cids))
            yield (file_id, _encode_ttf_with_side_effects(self.ttf))

    def _encode_bbox(f: TTFont, scale: float) -> atoms.Array:
        head = f["head"]
        return atoms.Array(
            atoms.Int(round(v * scale))
            for v in (head.xMin, head.yMin, head.xMax, head.yMax)
        )

    # See PDF 32000-1:2008, section 9.8.2
    class _FontDescriptorFlag(enum.IntFlag):
        FIXED_PITCH = 1 << 0
        SERIF = 1 << 1
        SYMBOLIC = 1 << 2
        SCRIPT = 1 << 3
        NONSYMBOLIC = 1 << 5
        ITALIC = 1 << 6
        ALL_CAP = 1 << 16
        SMALL_CAP = 1 << 17
        FORCE_BOLD = 1 << 18

    def _encode_flags(f: TTFont) -> atoms.Int:
        return atoms.Int(
            _FontDescriptorFlag.SYMBOLIC
            | (f["post"].isFixedPitch and _FontDescriptorFlag.FIXED_PITCH)
            | (bool(f["post"].italicAngle) and _FontDescriptorFlag.ITALIC)
            | (
                f["OS/2"].usWeightClass >= 600
                and _FontDescriptorFlag.FORCE_BOLD
            )
        )

    # WARNING: the act of saving fontTools' TTFont leads to changed properties
    # such as ttfont['head'].xMin. Beware of when you call this function!
    def _encode_ttf_with_side_effects(f: TTFont) -> atoms.Stream:
        tmp = BytesIO()
        f.save(tmp)
        content = tmp.getvalue()
        return atoms.Stream([content], [(b"Length1", atoms.Int(len(content)))])

    def _encode_cid_gid_map(ttf: TTFont, cids: Iterable[_CID]) -> atoms.Stream:
        # See PDF32000-1:2008 (table 117) for instructions on how this works.
        # Note that the Glyph IDs are different after subsetting!
        return atoms.Stream(
            map(
                pipe(
                    # CID -> Glyph name
                    dictget(ttf.getBestCmap() or {}, _REPLACEMENT_GLYPH),
                    # Glyph name -> Glyph ID
                    ttf.getReverseGlyphMap().__getitem__,
                    # Glyph ID -> bytes
                    methodcaller("to_bytes", 2, "big"),
                ),
                cids,
            )
        )

    # NOTE: the given widths must be ordered by continuously ascending
    # CID value from 0 onwards
    def _encode_widths(widths: Iterable[GlyphPt]) -> atoms.Array:
        # See PDF32000-1:2008 (9.7.4.3) for how character widths are encoded.
        # For now we choose to simply encode all widths sequentially.
        # FUTURE: It should be made more efficient for fixed width fonts.
        return atoms.Array(
            (atoms.Int(0), atoms.Array(map(pipe(int, atoms.Int), widths)))
        )

    def _encode_cap_height(f: TTFont, scale: float) -> atoms.Int:
        # Apparently not all TTF fonts properly have the capheight accessible.
        # We can fall back to the ascender height, which is usually slightly
        # lower. See https://fonts.google.com/knowledge/glossary/cap_height
        try:
            v = f["OS/2"].sCapHeight
        except AttributeError:
            v = f["hhea"].ascent

        return atoms.Int(round(v * scale))

    _FONTWEIGHT_TO_STEM_V_RATIO = (241 - 50) / (900 - 100)

    def _encode_stem_v(f: TTFont) -> atoms.Int:
        # See stackoverflow.com/questions/35485179.
        # The StemV value cannot be directly retrieved from TTF type fonts.
        # Common wisdom seems to be to map the font weight (100-900) to
        # reasonable StemV values (50-241).
        return atoms.Int(
            round(50 + _FONTWEIGHT_TO_STEM_V_RATIO * f["OS/2"].usWeightClass)
        )

    def _unicode_map(m: Collection[tuple[Ordinal, _CID]]) -> Iterable[bytes]:
        # The 'To Unicode' map ensures that the correct characters are copied
        # from a text selection.
        yield _TO_UNICODE_CMAP_PRE
        yield b"%i beginbfchar\n" % len(m)
        for code, cid in m:
            yield b"<%04X> <%b>\n" % (cid, _utf16be_hex(code))
        yield _TO_UNICODE_CMAP_POST

    # based on PDF32000-1:2008, page 294
    _TO_UNICODE_CMAP_PRE = b"""\
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
    """ % b"".join(
        _CIDSYS_INFO.write()
    )
    _TO_UNICODE_CMAP_POST = b"""\
    endbfchar
    endcmap
    CMapName currentdict /CMap defineresource pop
    end
    end"""
else:  # pragma: no cover
    FONTTOOLS_MISSING_EXCEPTION = NotImplementedError(
        "Embedded fonts require `fontTools` dependency. "
        "Install with pdfje[fonts]"
    )

    @add_slots
    @dataclass(frozen=True)
    class Subset(Font):
        @staticmethod
        def new(i: FontID, font: Path) -> Subset:
            raise FONTTOOLS_MISSING_EXCEPTION

        def width(self, s: str) -> Pt:
            raise FONTTOOLS_MISSING_EXCEPTION

        def encode(self, s: str) -> bytes:
            raise FONTTOOLS_MISSING_EXCEPTION

        def kern(self, s: str) -> Iterable[tuple[int, GlyphPt]]:
            raise FONTTOOLS_MISSING_EXCEPTION
