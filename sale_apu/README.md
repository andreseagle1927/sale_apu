# APU for Quotations

`sale_apu` adds an internal APU tab to Odoo 18 Community sale quotations and orders. It lets Sales users track internal product costs on quotation-specific APU lines without exposing those costs on the customer quotation PDF.

## What it does

- Adds an `APU` tab on `sale.order`
- Lets authorized users enter internal cost lines with product, description, quantity, UoM, unit cost, and subtotal
- Copies `product.standard_price` into `unit_cost` when a product is selected
- Stores the copied cost as a historical snapshot on the APU line
- Computes:
  - total APU
  - expected profit
  - margin percentage
- Keeps APU data internal to Sales users with access
- Duplicates APU lines when a quotation is duplicated
- Deletes APU lines when the quotation is deleted

## Installation

1. Copy the `sale_apu` folder into your custom addons path.
2. Update the Apps list in Odoo.
3. Install `APU for Quotations`.

## Usage

1. Open a quotation or sale order.
2. Open the `APU` tab.
3. Add one or more APU lines.
4. Select a product to snapshot its current internal cost into `Unit Cost`.
5. Adjust `Unit Cost` manually if needed.

The module computes:

- `Total APU`
- `Expected Profit`
- `Margin (%)`

## Upgrade

```bash
odoo-bin -d <database_name> -u sale_apu
```

## Main Fields

On `sale.order`:

- `apu_line_ids`
- `apu_total`
- `apu_expected_profit`
- `apu_margin_percent`

On `sale.order.apu.line`:

- `sale_order_id`
- `sequence`
- `product_id`
- `name`
- `product_uom_id`
- `quantity`
- `unit_cost`
- `subtotal`
- `currency_id`
- `company_id`

## Security Behavior

- The module defines the `APU / View Costs` security group.
- APU tab content and cost totals are only shown to users in that group or Sales administrators.
- Internal Sales users have access rights to the APU line model.
- Portal and public users do not get access to APU cost fields through the normal quotation PDF or backend views.
