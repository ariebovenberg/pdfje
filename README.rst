🖍 PDFje
========

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

  **PDF·je** [PDF·yuh] *(noun)* Dutch for 'small PDF'

Tiny library for writing simple PDFs. Experimental.

Currently under development.
Leave a ⭐️ on GitHub if you're interested how this develops!

Why?
----

The most popular libraries for writing PDFs are quite old and inspired by Java and PHP.
*PDFje* aims to be a modern, Pythonic library with a more declarative API.

How does it work?
-----------------

.. code-block:: python

  >>> from pdfje import Document, Page, Text
  >>> pdf.Document([
  ...     Page([Text("Hello", at=(200, 700)), Text("World", at=(300, 670))]),
  ...     Page(),
  ...     Page([Text("This is the last page!", at=(300, 600))]),
  ...
  ... ]).to_path('hello.pdf')

See `the docs <https://pdfje.rtfd.io>`_ for a complete overview.

Installation
------------

It's available on PyPI.

.. code-block:: bash

  pip install pdfje
