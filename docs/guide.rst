User guide
==========

Documents and pages
-------------------

PDF documents consist of pages, which may have graphical context (e.g. text).
Below shows an example of creating a document and writing it to a file.

.. code-block:: python

  >>> from pdfje import Document, Page, Text
  >>> Document([
  ...     Page([Text("Hello", at=(200, 700)), Text("World", at=(300, 670))]),
  ...     Page(),  # empty page
  ...     Page([Text("This is the last page!", at=(300, 600))]),
  ... ]).to_path('hello.pdf')


Fonts and unicode
-----------------

There are two types of fonts:

1. **Standard fonts** are included in all PDF readers.
   The downside is that these fonts only support a very
   limited set of unicode characters.
   The standard fonts are:

   - Helvetica
   - Times Roman
   - Courier
   - Symbol
   - ZapfDingBats

   Below is an example of using different standard fonts:

   .. code-block:: python

      >>> from pdfje import Text, courier, helvetica
      >>> Text("Hello Helvetica", font=helvetica)
      >>> Text("Ciao, Courier", font=courier)

   .. warning::

     The standard fonts only support characters within the ``cp1252`` encoding
     (i.e. ASCII plus some common western european characters).
     This is a limitation of the PDF format, not ``pdfje``.
     Characters outside this set will be displayed as ``?``.
     If you need broader unicode support,
     you will need to use :ref:`an embedded font<embedded-fonts>`.

.. _embedded-fonts:

2. **Embedded fonts** are included in the PDF file itself.
   To use an embedded font, you will need to download its TrueType
   (``.ttf``) font file and tell ``pdfje`` where to find it.

   Here is an example of using the DejaVu font

   .. code-block:: python

      >>> from pdfje import Text, Font
      >>> dejavu = Font.from_path("path/to/DejaVuSansCondensed.ttf")
      >>> Text("We meet again, DejaVu!", font=dejavu)

   .. note::

      To save space, only the parts of the font that are actually used will
      be embedded in the document.
      This standard practice is called "subsetting".

   .. note::

      Any unicode characters for which a font has no representation
      will be displayed as a 'missing character' box.
