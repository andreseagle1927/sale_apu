APU for Quotations
==================

``sale_apu`` adds an internal APU tab to Odoo 18 Community sale quotations and orders. It lets Sales users track internal product costs on quotation-specific APU lines without exposing those costs on the customer quotation PDF.

What it does
------------

* Adds an ``APU`` tab on ``sale.order``
* Mirrors quotation ``product`` / ``section`` / ``note`` lines into the APU tab automatically
* Keeps mirrored APU rows synced one-way from quotation lines while leaving manual APU rows independent
* Lets authorized users enter internal cost lines with product, description, quantity, UoM, unit cost, and subtotal
* Supports section lines, note lines, and an internal product catalog picker inside the APU tab
* Copies ``product.standard_price`` into ``unit_cost`` when a product is selected
* Stores the copied cost as a historical snapshot on the APU line
* Computes:
  * total APU
  * expected profit
  * margin percentage
* Provides an internal ``Internal APU Report`` printout for quotations and sale orders
* Keeps APU data internal to Sales users with access
* Duplicates APU lines when a quotation is duplicated
* Deletes APU lines when the quotation is deleted

Installation
------------

* Copy the ``sale_apu`` folder into your custom addons path.
* Update the Apps list in Odoo.
* Install ``APU for Quotations``.

Usage
-----

* Open a quotation or sale order.
* Open the ``APU`` tab.
* Add one or more APU lines, or use ``Add a section``, ``Add a note``, or ``Catalog``.
* Select a product to snapshot its current internal cost into ``Unit Cost``.
* Adjust ``Unit Cost`` manually if needed.

The module computes total APU, expected profit, and margin percentage.

Upgrade
-------

Use ``odoo-bin -d <database_name> -u sale_apu`` to upgrade the module.

Main Fields
-----------

On ``sale.order``:

* ``apu_line_ids``
* ``apu_total``
* ``apu_expected_profit``
* ``apu_margin_percent``

On ``sale.order.apu.line``:

* ``sale_order_id``
* ``sequence``
* ``product_id``
* ``name``
* ``product_uom_id``
* ``quantity``
* ``unit_cost``
* ``subtotal``
* ``currency_id``
* ``company_id``

Security Behavior
-----------------

* The module defines the ``APU / View Costs`` security group.
* APU tab content and cost totals are only shown to users in that group or Sales administrators.
* Internal Sales users have access rights to the APU line model.
* Portal and public users do not get access to APU cost fields through the normal quotation PDF or backend views.
