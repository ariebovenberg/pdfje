Changelog
=========

0.5.0 (2023-??-??)
------------------

**Breaking**

- 🪆 Expose most classes from submodules instead of root
  (e.g. ``pdfje.Rect`` becomes ``pdfje.draw.Rect``).
  The new locations can be found in the API documentation.
- ``Rule`` ``padding`` attribute renamed to ``margin``.

**Added**

- 📰 Support for horizontal alignment and justification of text.
- 🫸 Support for indenting the first line of a paragraph.
- ✂️  Automatic hyphenation of text.

0.4.0 (2023-04-10)
------------------

A big release with lots of new features and improvements.
Most importantly, the page layout engine is now complete and
can be used to create multi-page/column documents.

**Added**

- 📖 Automatic layout of multi-style text into lines, columns, and pages
- 🔬 Automatic kerning for supported fonts
- 🖌️ Support for drawing basic shapes
- 🎨 Additional text styling options
- 📦 Make fonttools dependency optional
- 📏 Horizontal rule element

**Documentation**

- 🧑‍🏫 Add a tutorial and examples
- 📋 Polished docstrings in public API

**Performance**

- ⛳️ Document pages and fonts are now written in one efficient pass

**Breaking**

- 🌅 Drop Python 3.7 support

0.3.0 (2022-12-02)
------------------

**Added**

- 🍰 Documents can be created directly from string input
- 🪜 Support for explicit newlines in text
- 📢 ``Document.write()`` supports paths, file-like objects and iterator output
- ✅ Improved PDF spec compliance

**Changed**

- 📚 Text is now positioned automatically within a page

0.2.0 (2022-12-01)
------------------

**Added**

- 🖌️ Different builtin fonts can be selected
- 📥 Truetype fonts can be embedded
- 🌏 Support for non-ASCII text
- 📐 Pages can be rotated
- 🤏 Compression is applied to keep filesize small

0.1.0 (2022-11-02)
------------------

**Added**

- 💬 Support basic ASCII text on different pages

0.0.1 (2022-10-28)
------------------

**Added**

- 🌱 Write a valid, minimal, empty PDF file
