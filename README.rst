ð pdf'je
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

  **pdfÂ·je** [`ð <https://upload.wikimedia.org/wikipedia/commons/a/ac/Nl-pdf%27je.ogg>`_ PDFÂ·yuh] (noun) Dutch for 'small PDF'

Tiny library for writing simple PDFs.

Currently under development.
The API may change significantly until the 1.x release.
Leave a â­ï¸ on GitHub if you're interested how this develops!

ðââï¸ Why?
----------

The most popular Python libraries for writing PDFs are quite old
and inspired by Java and PHP. **pdf'je** is a modern, Pythonic library with
a more declarative API.

ð How does it work?
--------------------

Getting text on paper is super easy:

.. code-block:: python

  from pdfje import Document
  Document("OlÃ¡ Mundo!").write('hello.pdf')

but you can of course do more:

.. code-block:: python

  from pdfje import Page, Text, Font

  Document([
      Page("""Simple is better than complex.
              Complex is better than complicated."""),
      Page(),
      Page(["The following text is",
            Text("bigger and fancier!",
                 font=Font.from_path('path/to/MyFont.ttf'),
                 size=20)])
  ]).write('hello.pdf')


See `the docs <https://pdfje.rtfd.io>`_ for a complete overview.

ð©ââï¸ Is pdf'je right for me?
------------------------------

Try it if you:

- ð¯ Just want to get simple text into a PDF quickly
- ðª Prefer coding in a declarative and Pythonic style
- ð Are looking for a lightweight, permissively licensed library
- ð­ Enjoy experimenting and contributing to something new

Look elsewhere if you:

- ð¸ï¸ Want to turn HTML into PDF -- use ``wkhtmltopdf`` instead
- ð¬ Need perfectly typeset documents -- use LaTeX instead
- ð Want lots of features -- use ``reportlab`` or ``fpdf2`` instead
- âï¸  Need to parse or edit -- use ``PyPDF2`` or ``pdfsyntax`` instead

ð¥ So, what's cooking?
----------------------

The following features are planned:

- ð Automatic line/page breaks
- ð¨ ``rich``-inspired styles and inline markup
- ð¼ï¸ Support for images
- âï¸  Basic drawing operations
- ð Bookmarks and links

ð Installation
---------------

It's available on PyPI.

.. code-block:: bash

  pip install pdfje

ð ï¸ Development
--------------

- Install dependencies with ``poetry install``.
- To write output files during tests, use ``pytest --output-path=<outpur-dir>``
