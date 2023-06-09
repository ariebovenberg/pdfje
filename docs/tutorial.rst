Tutorial
========

This guide will walk you through the basics of using **pdfje**.
Each section will build on the previous one, so it is recommended to read
the sections in order.

You can also read the :ref:`API Reference <api>` for more details.
Or, if you prefer, you can skip straight to the :ref:`examples <examples>`.


🌱 The minimal document
-----------------------

Let's start with a very simple PDF document:

.. code-block:: python

  from pdfje import Document
  Document("It was a dark and stormy night...").write("my-story.pdf")

This bit of code will:

- Apply the standard font and styling (Helvetica, 12pt) to the given string.
- Layout the text onto A4-sized pages, automatically adding pages as needed
- Write the document to a file named ``my-story.pdf``

The following sections will explain how to expand on this example.

.. _style:

🎨 Styling text
---------------

In the previous example,

.. code-block:: python

   Document("It was a dark and stormy night...")

is actually shorthand for:

.. code-block:: python

   from pdfje.layout import Paragraph
   Document(Paragraph("It was a dark and stormy night..."))

With :class:`~pdfje.layout.Paragraph`, you can add styling:

.. code-block:: python

   from pdfje.style import Style
   from pdfje.fonts import times_roman
   paragraph = Style(font=times_roman, size=10, color="#003333")
   chapter_one = Paragraph("It was a dark and stormy night...", style=paragraph)

Stacking styles
~~~~~~~~~~~~~~~

Styles can build on each other using the ``|`` operator.
For example, you can define a style on top of the paragraph style:

.. code-block:: python

   big_emphasis = paragraph | Style(size=15, italic=True)

Styling within a paragraph
~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also apply multiple styles to various parts of a single paragraph,
by passing several strings and/or :class:`~pdfje.style.Span` instances to the constructor:

.. code-block:: python

   from pdfje.style import Span
   chapter_one = Paragraph(
       [
           "It was a ",
           Span("dark", bold),
           " and ",
           Span("stormy", big_emphasis),
           " night...",
       ],
       style=paragraph,
   )

This will render text as follows:

..

   .. raw:: html

      <span style="font-size: 10pt;">It was a <span style="font-weight: bold;">dark</span> and <span style="font-size: 15pt; font-style: italic;">stormy</span> night...</span>

Styles inside nested :class:`~pdfje.style.Span` objects will build on the style
of their parent. Span objects can be nested as deep as you like.

Style Shortcuts
~~~~~~~~~~~~~~~

Below are a few tips to make it easier to work with styles.

Firstly, ``bold`` and ``italic`` are predefined styles:

.. code-block:: python

   from pdfje.style import bold, italic  # equivalent to Style(italic=True)

Secondly, you can use fonts and colors directly as styles:

.. code-block:: python

   Span("Hello world", times_roman)
   # is equivalent to:
   Span("Hello world", Style(font=times_roman))

   # combine with other styles:
   mystyle = bold | times_roman | "#ff0000"

Lastly, you can adjust the default style at document level:

.. code-block:: python

   doc = Document("Hello world", style=Style(font=times_roman, line_spacing=1.4))

📑 Pages
--------

Now that we know how text can be styled,
let's look at how to customize the document and page layout.

Automatic pages
~~~~~~~~~~~~~~~

Starting where we left off in the previous section, we can reveal that

.. code-block:: python

   Document(chapter_one)

is actually shorthand for:

.. code-block:: python

   from pdfje import AutoPage
   Document([
       AutoPage([chapter_one]),
   ])

:class:`~pdfje.AutoPage` takes a list of elements to layout and
creates pages automatically as needed.
The most common blocks are paragraphs of text.
Here is an example of creating an auto page with various blocks of text.

.. code-block:: python

  from pdfje import AutoPage
  from pdfje.layout import Rule
  main_story = AutoPage([
      Paragraph("Chapter one: The beginning", style=heading),
      Paragraph("It was a dark and stormy night...", paragraph),
      Rule(),  # a horizontal line
      Paragraph("Chapter two: the adventure continues", heading),
      Paragraph(MORE_TEXT, paragraph),
      ...,
  ])

Now, what if we want to add a single title page to our document?
We will discuss how to do this in the next section.

Single pages
~~~~~~~~~~~~

While :class:`~pdfje.AutoPage` positions elements automatically and
generates pages as needed,
:class:`~pdfje.Page` objects represent a single page, on which
each element is positioned explicitly.

Here is an example of a title page for our story, on A5-sized paper:

.. code-block:: python

    from pdfje import Page
    from pdfje.units import A5
    from pdfje.draw import Line, Text, Rect

    title_page = Page(
        [
            # Some nice shapes
            Rect(
                (A5.x / 2 - 200, 200),  # use page dimensions to center it
                width=400,
                height=100,
                fill="#99aaff",
                stroke=None,
            ),
            Ellipse((A5.x / 2, 200), 300, 100, fill="#22d388"),
            # The title on top of the shapes
            Text(
                (A5.x / 2, 230),
                "My awesome title",
                Style(size=30, bold=True),
                align="center",
            )
        ],
        size=A5,
    )

This page can be added to a document alongside :class:`~pdfje.AutoPage` objects:

.. code-block:: python

  doc = Document([title_page, main_story])

See the :class:`~pdfje.Page` class for more details on customizing pages.

.. admonition:: The page coordinate system

   The coordinate system is a cartesian plane with the origin at the bottom left of the page.
   Sizes are specified in points (1/72 inch).

   There are several helpers to convert between points and other units:

   .. code-block:: python

     from pdfje.units import inch, pc, cm, mm, pt
     inch(1)  # 72
     pc(1)  # 12
     cm(1)  # 28.346
     mm(1)  # 2.835
     pt(1)  # 1 -- no conversion needed but can be useful for explicitness

   Standard page sizes are available in the :mod:`pdfje.units` module.

   .. code-block:: python

     from pdfje.units import A4, A5, A6, letter, legal, tabloid


Page templates
~~~~~~~~~~~~~~

The :class:`~pdfje.AutoPage` class has a ``template`` argument,
which allows you to specify a :class:`~pdfje.Page` to use as a template
for each page.
This can be used to draw a header or footer to each page, or add page numbers.
Additionally, you can customize the column layout for each page.

As a first step, let's use this feature to set a smaller page size for our story:

.. code-block:: python

    template = Page(size=A5, margin=(mm(20), mm(20), mm(25)))

    main_story = AutoPage([...], template=template)


Let's expand this template to add a header and footer to each page:

.. code-block:: python

    template = Page(
        [
            # Our story title at the top left of the page
            Text((mm(20), A5.y - 20), "My awesome title", Style(size=8, italic=True)),
            # A line at the bottom of the page
            Line((mm(20), mm(20)), (A5.x - mm(20), mm(20)), stroke="#aaaaaa"),
        ],
        size=A5,
        margin=(mm(20), mm(20), mm(25)),
    )

Finally, let's add a page number to the footer. This will require each
page to be drawn individually (each page number is of course different).
We can do this by passing an *callable* which takes a page number,
and returns a :class:`~pdfje.Page`.

.. code-block:: python

    def create_page(num: int) -> Page:
        # add() creates a copy of the page with the given elements added.
        return template.add(
            # the page number at the bottom of the page
            Text((A5.x / 2, mm(20)), str(num), Style(size=8), align="center")
        )

    main_story = AutoPage(..., template=create_page)

Another advanced feature of page templates is the ability to customize
the column layout for each page.
This is useful for creating multi-column layouts.
You can read more about this in :ref:`the multi-column example <multi-column>`.

🖋️ Fonts
--------

We've already seen fonts in action in the previous section.
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

      from pdfje.fonts import courier, helvetica
      heading = Style(font=helvetica, size=20, bold=True)
      Span("Ciao, Courier", style=courier)

   .. note::

     The standard fonts only support characters within the ``cp1252`` encoding
     (i.e. ASCII plus some common western european characters).
     This is a limitation of the PDF format, not pdfje.
     Characters outside this set will be displayed as ``?``.
     If you need broader unicode support,
     you will need to use :ref:`an embedded font<embedded-fonts>`.

.. _embedded-fonts:

2. **Embedded fonts** are included in the PDF file itself.
   To use an embedded font, you will need to obtain its TrueType
   (``.ttf``) font file and tell pdfje where to find it.

   Here is an example of using the DejaVu font:

   .. code-block:: python

      from pdfje.fonts import TrueType
      dejavu = TrueType(
          "path/to/DejaVuSansCondensed.ttf",
          bold="path/to/DejaVuSansCondensed-Bold.ttf",
          italic="path/to/DejaVuSansCondensed-Oblique.ttf",
          bold_italic="path/to/DejaVuSansCondensed-BoldOblique.ttf",
      )
      Span("We meet again, DejaVu!", style=dejavu)

   .. note::

      * To save space, only the parts of the font that are actually used will
        be embedded in the document.
        This standard practice is called "subsetting".
      * Any unicode characters for which a font has no representation
        will be displayed as a 'missing character' box.


✂️ Hyphenation
--------------

Hyphenation can be customized by using the optional `Pyphen <https://www.courtbouillon.org/pyphen>`_ dependency.

Install it with:

.. code-block:: bash

  pip install pdfje[hyphens]

To customize hyphenation, pass a :class:`~pyphen.Pyphen` object to the
:class:`~pdfje.style.Style` constructor:

.. code-block:: python

  from pyphen import Pyphen
  dutch_hyphens = Pyphen(lang="nl_NL")
  Span("Lastige lettergrepen!", Style(hyphens=dutch_hyphens))

.. note::

   - If you don't have ``pyphen`` installed, pdfje will use a simple
     hyphenation algorithm for english text.

   - To disable hyphenation altogether,
     pass ``hyphens=None`` to the :class:`~pdfje.Style` constructor.

🧮 Optimal line breaks
----------------------

Breaking paragraphs into lines is `more complex than it seems <https://www.youtube.com/watch?v=kzdugwr4Fgk>`_.
A naive approach often leads to uneven line lengths and excessive or awkward hypenation.
Pdfje uses the `Knuth-Plass <https://en.wikipedia.org/wiki/Line_wrap_and_word_wrap#Knuth.E2.80.93Plass_algorithm>`_
algorithm to find the optimal line breaks.
This algorithm is used by most typesetting systems, including TeX and InDesign.
Pdfje's implementation optimizes for:

- Filling the lines as evenly as possible
- Avoiding hyphenation in general, especially if the previous line is also hyphenated

A disadvantage of the Knuth-Plass algorithm is that it is relatively slow.
If you'd like to use a faster, but less optimal algorithm, you can pass
``optimal=False`` to the :class:`~pdfje.layout.Paragraph` constructor.

🛟 Avoiding orphaned lines
--------------------------

Orphaned or widowed lines are lines that are left dangling at the top or bottom of a page.
They are considered bad typography, and should be avoided.

There are many ways to avoid orphaned lines, but the most common one is to
move a line to the next page if it avoids a line being left alone.
pdfje supports this behavior by default.
If you want to disable this behavior, pass ``avoid_orphans=False`` to the
:class:`~pdfje.layout.Paragraph` constructor.
This is useful in multi-column layouts, where you want to avoid uneven columns.
