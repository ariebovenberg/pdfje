🌷 pdf'je
=========

.. image:: https://img.shields.io/pypi/v/pdfje.svg?style=flat-square&color=blue
   :target: https://pypi.python.org/pypi/pdfje

.. image:: https://img.shields.io/pypi/pyversions/pdfje.svg?style=flat-square
   :target: https://pypi.python.org/pypi/pdfje

.. image:: https://img.shields.io/pypi/l/pdfje.svg?style=flat-square&color=blue
   :target: https://pypi.python.org/pypi/pdfje

.. image:: https://img.shields.io/badge/mypy-strict-forestgreen?style=flat-square
   :target: https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-strict

.. image:: https://img.shields.io/badge/coverage-99%25-forestgreen?style=flat-square
   :target: https://github.com/ariebovenberg/pdfje

.. image::  https://img.shields.io/github/actions/workflow/status/ariebovenberg/pdfje/tests.yml?branch=main&style=flat-square
   :target: https://github.com/ariebovenberg/pdfje

.. image:: https://img.shields.io/readthedocs/pdfje.svg?style=flat-square
   :target: http://pdfje.readthedocs.io/

..

  **pdf·je** [`🔉 <https://upload.wikimedia.org/wikipedia/commons/a/ac/Nl-pdf%27je.ogg>`_ PDF·yuh] (noun) Dutch for 'small PDF'

**Write beautiful PDFs in declarative Python.**

*(Currently in active development. Leave a* ⭐️ *on GitHub if you're interested how this develops!)*

Features
--------

Pdf'je distinguishes itself with the following combination of features:

🧩 Declarative API
~~~~~~~~~~~~~~~~~~

In most PDF writers, you first create empty objects and
then mutate them with methods like ``addText()``,
all while changing the state with methods like ``setFont()``.
**Pdf'je** is different. You describe the document you want to write,
and it takes care of the details. No state to manage, no mutations.
This makes your code easier to reuse and reason about.

.. code-block:: python

  from pdfje import Document
  Document("Olá Mundo!").write("hello.pdf")

See `the tutorial <https://pdfje.rtfd.io/en/latest/tutorial.html>`_
for a complete overview of features, including:

- Styling text including font, size, and color
- Automatic layout of text into one or more columns
- Builtin and embedded fonts
- Drawing basic shapes

See the roadmap_ for supported features.

📖 Decent typography
~~~~~~~~~~~~~~~~~~~~

Legibility counts — and `kerning <https://en.wikipedia.org/wiki/Kerning>`_
is a key part of this.
We've come to expect it everywhere, from web browsers to word processors.
However, most PDF writers don't support it.
By using the proper metadata,
**pdf'je** helps you write documents that look great.

.. image:: https://github.com/ariebovenberg/pdfje/raw/main/sample.png
   :alt: Sample document with two columns of text

🎈 Small footprint
~~~~~~~~~~~~~~~~~~

The PDF format supports many features, but most of the time you only need a few.
Why install many dependencies — just to write a simple document?
Not only is **pdf'je** pure-Python, it allows you to
install only the dependencies you need.

.. code-block:: bash

  pip install pdfje                 # no dependencies
  pip install pdfje[fonts, hyphens] # embedded fonts and improved hyphenation

.. _roadmap:

Roadmap
-------

**Pdf'je** is still in active development,
so it is not yet feature-complete.
Until the 1.0 version, the API may change with minor releases.

Features:

✅ = implemented, 🚧 = planned, ❌ = not planned

- Typesetting
    - ✅ Automatic kerning
    - ✅ Wrapping text into lines, columns, and pages
    - ✅ Page sizes
    - ✅ Centering text
    - ✅ Justification
    - ✅ Hyphenation
    - 🚧 Avoiding orphaned/widowed lines
    - 🚧 Tex-style line breaking
    - 🚧 Broader unicode support in text wrapping
- Drawing operations
    - ✅ Lines
    - ✅ Rectangles
    - ✅ Circles, ellipses
    - 🚧 Arbitrary paths, fills, and strokes
- Text styling
    - ✅ Font and size
    - ✅ Embedded fonts
    - ✅ Colors
    - ✅ Bold, italic
    - 🚧 Underline and strikethrough
    - 🚧 Superscript and subscript
    - ❌ Complex fill patterns
- 🚧 Images
- 🚧 Bookmarks and links
- 🚧 Tables
- 🚧 Bullet/numbered lists
- 🚧 Inline markup with Markdown (Commonmark/MyST)
- ❌ Emoji
- ❌ Tables of contents
- ❌ Forms
- ❌ Annotations

License
-------

This library is licensed under the terms of the MIT license.
It also includes short scripts from other projects (see ``pdfje/vendor``),
which are either also MIT licensed, or in the public domain.

Contributing
------------

Here are some useful tips for developing in the ``pdfje`` codebase itself:

- Install dependencies with ``poetry install``.
- To write output files during tests, use ``pytest --output-path=<outpur-dir>``
- To also run more comprehensive but 'slow' tests, use ``pytest --runslow``

Acknowledgements
----------------

**pdf'je** is inspired by the following projects.
If you're looking for a PDF writer, you may want to check them out as well:

- `python-typesetting <https://github.com/brandon-rhodes/python-typesetting>`_
- `fpdf2 <https://pyfpdf.github.io/fpdf2/index.html>`_
- `ReportLab <https://www.reportlab.com/>`_
- `WeasyPrint <https://weasyprint.org/>`_
- `borb <httpsL//github.com/jorisschellekens/borb/>`_
- `wkhtmltopdf <https://wkhtmltopdf.org/>`_
- `pydyf <https://github.com/CourtBouillon/pydyf>`_
