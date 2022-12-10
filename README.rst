🌷 pdf'je
=========

.. image:: https://img.shields.io/pypi/v/pdfje.svg?style=flat-square
   :target: https://pypi.python.org/pypi/pdfje

.. image:: https://img.shields.io/pypi/l/pdfje.svg?style=flat-square
   :target: https://pypi.python.org/pypi/pdfje

.. image:: https://img.shields.io/pypi/pyversions/pdfje.svg?style=flat-square
   :target: https://pypi.python.org/pypi/pdfje

.. image:: https://img.shields.io/readthedocs/pdfje.svg?style=flat-square
   :target: http://pdfje.readthedocs.io/

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square
   :target: https://github.com/psf/black

-----

  **pdf·je** [`🔉 <https://upload.wikimedia.org/wikipedia/commons/a/ac/Nl-pdf%27je.ogg>`_ PDF·yuh] (noun) Dutch for 'small PDF'

Write beautiful PDFs in declarative Python.

Currently in active development. See the roadmap_ for supported features.
Leave a ⭐️ on GitHub if you're interested how this develops!

Why?
----

There are many PDF libraries for Python, but none of them
have these features:

🧩 Declarative API
~~~~~~~~~~~~~~~~~~

In most PDF writers, you first create various empty objects and
then mutate them with methods like ``addText()``,
all while changing the state of the writer with methods like ``setFont()``.
**Pdf'je** is different. You describe the document you want to write,
and the library takes care of the details. No state to manage, no mutations.
This makes your code easier to reuse and reason about.

📐 Polished typography
~~~~~~~~~~~~~~~~~~~~~~

Legibility counts. And `kerning <https://en.wikipedia.org/wiki/Kerning>`_
— i.e. adjusting the spacing between letters — is a key part of this.
Automatic kerning is supported everywhere, from web browsers to word processors.
However, most PDF writers don't support it.
By using font metrics to calculate the correct kerning,
**pdf'je** helps you write documents that look great.

🎈 Small footprint
~~~~~~~~~~~~~~~~~~

PDF supports many features, but most of the time you only need a few.
Why install many dependencies — just to write a simple document?
Not only is **pdf'je** pure-Python, it allows you to
install only the dependencies you need.


Quickstart
----------

Getting text onto paper is super easy:

.. code-block:: python

  from pdfje import Document
  Document("Olá Mundo!").write("hello.pdf")

See `the tutorial <https://pdfje.rtfd.io/en/latest/tutorial.html>`_
for a complete overview of features, including:

- Styling text including font, size, and color
- Automatic layout of text into one or more columns
- Builtin and embedded fonts
- Drawing basic shapes

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
    - 🚧 Centering text
    - 🚧 Justification
    - 🚧 Hyphenation
    - 🚧 Avoiding orphaned lines
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
- 🚧 Inline markup with Markdown (Commonmark/MyST)
- ❌ Emoji
- ❌ Tables of contents
- ❌ Forms
- ❌ Annotations

Installation
------------

It's available on PyPI.

.. code-block:: bash

  pip install pdfje

By default, no additional dependencies are installed.
If you'd like to use custom fonts, you'll need ``fontTools``,
which is included in the ``[fonts]`` extras:

.. code-block:: bash

   pip install pdfje[fonts]

License
-------

This library is licensed under the terms of the MIT license.
It also includes short scripts from other projects (see ``pdfje/vendor``),
which are also MIT licensed.

Contributing
------------

Here are some useful tips for developing in the ``pdfje`` codebase itself:

- Install dependencies with ``poetry install``.
- To write output files during tests, use ``pytest --output-path=<outpur-dir>``
- To also run more comprehensive but 'slow' tests, use ``pytest --runslow``

Alternatives
------------

If pdf'je doesn't suit your needs, here are some other options:

- PyFPDF
- ReportLab
- WeasyPrint
- borb
- wkhtmltopdf
- pydyf
