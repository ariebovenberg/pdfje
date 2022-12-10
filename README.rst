🖍 pdf'je
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

Tiny library for writing simple PDFs.

Currently under development.
The API may change significantly until the 1.x release.
Leave a ⭐️ on GitHub if you're interested how this develops!

💁‍♂️ Why?
----------

Unlike other Python PDF writers, **pdf'je** provides:

- 🚲 A small footprint — dependencies optional
- 🪄 A declarative API
- 👌 Support for `kerning <https://en.wikipedia.org/wiki/Kerning>`_
- 🪁 A permissive license

That said, pdf'je is a new library, so it doesn't support a lot of
advanced features. If you need these, you should check out
other PDF writers such as ``reportlab``, ``fpdf2``, or ``borb``.

🚀 How does it work?
--------------------

Getting text on paper is super easy:

.. code-block:: python

  from pdfje import Document
  Document("Olá Mundo!").write('hello.pdf')

but you can of course do more:

.. code-block:: python

  from pdfje import Page, AutoPage, String, Font, Rect
  from io import BytesIO

  Document(
    [
      AutoPage(Text(long_bit_of_text)),  # automatic line/page breaks
      Page(),  # blank page
      Page(
        [
          String(
            "big and fancy text!",
            font=Font.from_path('path/to/MyFont.ttf'),
            size=20
          ),
          Rect((50, 50), width=400, height=200)
        ]
      )
    ]
  ).write(target:= BytesIO())  # write to any file-like object


See `the docs <https://pdfje.rtfd.io>`_ for a complete overview.

🥘 What's cooking?
----------------------

The following features are planned:

- Inline markup with Markdown (Commonmark/MyST)
- Support for images
- Bookmarks and links

🎁 Installation
---------------

It's available on PyPI.

.. code-block:: bash

  pip install pdfje

By default, no additional dependencies are installed.
If you're making use of custom fonts, you'll need ``fontTools``,
which is included in the ``[fonts]`` extras:

.. code-block:: bash

   pip install pdfje[fonts]

🛠️ Development
--------------

- Install dependencies with ``poetry install``.
- To write output files during tests, use ``pytest --output-path=<outpur-dir>``
- To also run more comprehensive but 'slow' tests, use ``pytest --runslow``
