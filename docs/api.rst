.. _api:

API reference
=============

Unless otherwise noted, all classes are immutable.

pdfje
-----

.. automodule:: pdfje
   :members:

pdfje.style
-----------

.. automodule:: pdfje.style
   :members:

.. autodata:: pdfje.style.bold
.. autodata:: pdfje.style.italic
.. autodata:: pdfje.style.regular

pdfje.layout
------------

.. automodule:: pdfje.layout
   :members:

pdfje.draw
----------

.. automodule:: pdfje.draw
   :members:

pdfje.fonts
-----------

.. autodata:: pdfje.fonts.helvetica
.. autodata:: pdfje.fonts.times_roman
.. autodata:: pdfje.fonts.courier
.. autodata:: pdfje.fonts.symbol
.. autodata:: pdfje.fonts.zapf_dingbats

.. automodule:: pdfje.fonts
   :members:


pdfje.units
-----------

.. automodule:: pdfje.units
   :members:


**Page sizes**

Below are common page sizes.
Because the page size is a :class:`~pdfje.XY` object, you can use
``x`` and ``y`` attributes to get the width and height of a page size.
The landscape variants can be obtained by calling :meth:`~pdfje.XY.flip`.

.. code-block:: python

   from pdfje.units import A4

   A4.x       # 595
   A4.y       # 842
   A4.flip()  # XY(842, 595) -- the landscape variant
   A4 / 2     # XY(297.5, 421) -- point at the center of the page

.. autodata:: pdfje.units.A0
.. autodata:: pdfje.units.A1
.. autodata:: pdfje.units.A2
.. autodata:: pdfje.units.A3
.. autodata:: pdfje.units.A4
.. autodata:: pdfje.units.A5
.. autodata:: pdfje.units.A6
.. autodata:: pdfje.units.letter
.. autodata:: pdfje.units.legal
.. autodata:: pdfje.units.tabloid
.. autodata:: pdfje.units.ledger
