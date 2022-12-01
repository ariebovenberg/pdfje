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

The most popular Python libraries for writing PDFs are quite old
and inspired by Java and PHP. **pdf'je** is a modern, Pythonic library with
a more declarative API.

🚀 How does it work?
--------------------

Getting text on paper is super easy:

.. code-block:: python

  from pdfje import Document
  Document("Olá Mundo!").write('hello.pdf')

but you can of course do more:

.. code-block:: python

  from pdfje import Page, Text, Font

  myfont = Font.from_path('path/to/MyFont.ttf')
  Document([
      Page("""Simple is better than complex.
              Complex is better than complicated."""),
      Page(),
      Page(Text("This text is bigger and fancier!", font=myfont, size=20))
  ]).write('hello.pdf')


See `the docs <https://pdfje.rtfd.io>`_ for a complete overview.

👩‍⚕️ Is pdf'je right for me?
------------------------------

Try it if you:

- 🎯 Just want to get simple text into a PDF quickly
- 🪄 Prefer coding in a declarative and Pythonic style
- 🎁 Are looking for a lightweight, permissively licensed library
- 🔭 Enjoy experimenting and contributing to something new

Look elsewhere if you:

- 🕸️ Want to turn HTML into PDF -- use ``wkhtmltopdf`` instead
- 🔬 Need perfectly typeset documents -- use LaTeX instead
- 🚚 Want lots of features -- use ``reportlab`` or ``fpdf2`` instead
- ✂️  Need to parse or edit -- use ``PyPDF2`` or ``pdfsyntax`` instead

🥘 So, what's cooking?
----------------------

The following features are planned:

- 📑 Automatic line/page breaks
- 🎨 ``rich``-inspired styles and inline markup
- 🖼️ Support for images
- ✏️  Basic drawing operations
- 🔗 Bookmarks and links

🎁 Installation
---------------

It's available on PyPI.

.. code-block:: bash

  pip install pdfje

🛠️ Development
--------------

- Install dependencies with ``poetry install``.
- To write output files during tests, use ``pytest --output-path=<outpur-dir>``
