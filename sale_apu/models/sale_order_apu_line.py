from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaleOrderApuLine(models.Model):
    _name = "sale.order.apu.line"
    _description = "Sale Order APU Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    display_type = fields.Selection(
        selection=[
            ("line_section", "Section"),
            ("line_note", "Note"),
        ],
        default=False,
        help="Technical field for UX purpose.",
    )
    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Quotation",
        required=True,
        ondelete="cascade",
        index=True,
        check_company=True,
    )
    source_order_line_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Source Order Line",
        ondelete="cascade",
        index=True,
        copy=False,
        check_company=True,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="sale_order_id.currency_id",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        related="sale_order_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        check_company=True,
        index=True,
    )
    name = fields.Char(string="Description", required=True)
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit of Measure",
        required=False,
    )
    quantity = fields.Float(
        string="Quantity",
        default=1.0,
        digits="Product Unit of Measure",
    )
    unit_cost = fields.Monetary(
        string="Unit Cost",
        currency_field="currency_id",
        default=0.0,
        groups="sale_apu.group_apu_view_costs,sales_team.group_sale_manager",
    )
    subtotal = fields.Monetary(
        string="Cost Subtotal",
        currency_field="currency_id",
        compute="_compute_subtotal",
        store=True,
        readonly=True,
        groups="sale_apu.group_apu_view_costs,sales_team.group_sale_manager",
    )

    _sql_constraints = [
        (
            "apu_display_type_consistency",
            "CHECK(display_type IS NOT NULL OR (product_id IS NOT NULL AND product_uom_id IS NOT NULL))",
            "Product and unit of measure are required on product lines.",
        ),
        (
            "apu_display_line_null_fields",
            "CHECK(display_type IS NULL OR (product_id IS NULL AND product_uom_id IS NULL AND quantity = 0 AND unit_cost = 0))",
            "Display lines cannot have product, quantity or cost values.",
        ),
        ("quantity_non_negative", "CHECK(quantity >= 0)", "Quantity cannot be negative."),
        ("unit_cost_non_negative", "CHECK(unit_cost >= 0)", "Unit cost cannot be negative."),
        ("source_order_line_unique", "UNIQUE(source_order_line_id)", "Each order line can only have one mirrored APU line."),
    ]

    @api.onchange("display_type")
    def _onchange_display_type(self):
        for line in self:
            if line.display_type:
                line.product_id = False
                line.product_uom_id = False
                line.quantity = 0.0
                line.unit_cost = 0.0
            elif line.product_id:
                line._apply_product_snapshot()

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if not line.product_id or line.display_type:
                continue
            line._apply_product_snapshot()

    def action_add_from_catalog(self):
        order = self.env["sale.order"].browse(self.env.context.get("order_id"))
        if not order:
            return False
        return order.action_add_apu_from_catalog()

    @api.depends("display_type", "quantity", "unit_cost")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = 0.0 if line.display_type else line.quantity * line.unit_cost

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            display_type = vals.get("display_type", self.default_get(["display_type"]).get("display_type"))
            product_id = vals.get("product_id")
            if display_type:
                vals.setdefault("display_type", display_type)
                vals.setdefault("quantity", 0.0)
                vals.setdefault("unit_cost", 0.0)
                vals["product_id"] = False
                vals["product_uom_id"] = False
            elif product_id:
                product = self.env["product.product"].browse(product_id)
                order = self.env["sale.order"].browse(vals["sale_order_id"]) if vals.get("sale_order_id") else self.env["sale.order"]
                snapshot = self._get_product_snapshot_values(
                    product,
                    order.company_id if order else self.env.company,
                    order.currency_id if order else self.env.company.currency_id,
                    order.date_order.date() if order and order.date_order else fields.Date.context_today(self),
                )
                vals.setdefault("name", snapshot["name"])
                vals.setdefault("product_uom_id", snapshot["product_uom_id"])
                if "unit_cost" not in vals:
                    vals["unit_cost"] = snapshot["unit_cost"]
            prepared_vals_list.append(vals)
        return super().create(prepared_vals_list)

    def write(self, vals):
        if "display_type" in vals and self.filtered(lambda line: line.display_type != vals.get("display_type")):
            raise ValidationError("You cannot change the type of an APU line. Delete it and create a new one instead.")
        result = super().write(vals)
        if "product_id" in vals or "sale_order_id" in vals:
            for line in self:
                if line.display_type or line.source_order_line_id:
                    continue
                if line.product_id and line.sale_order_id:
                    line._apply_product_snapshot()
        return result

    def _apply_product_snapshot(self):
        self.ensure_one()
        if self.display_type:
            return
        snapshot = self._get_product_snapshot_values(
            self.product_id,
            self.sale_order_id.company_id or self.env.company,
            self.sale_order_id.currency_id or self.env.company.currency_id,
            self.sale_order_id.date_order.date() if self.sale_order_id.date_order else fields.Date.context_today(self),
        )
        self.name = snapshot["name"]
        self.product_uom_id = snapshot["product_uom_id"]
        self.unit_cost = snapshot["unit_cost"]

    def _get_product_snapshot_values(self, product, company, currency, price_date):
        company = company or self.env.company
        currency = currency or company.currency_id
        product = product.with_company(company).sudo()
        unit_cost = company.currency_id._convert(
            product.standard_price,
            currency,
            company,
            price_date,
        )
        return {
            "name": product.display_name,
            "product_uom_id": product.uom_id.id,
            "unit_cost": unit_cost,
        }

    def _get_product_catalog_lines_data(self, parent_record=False, **kwargs):
        if not self:
            return {
                "quantity": 0.0,
                "price": 0.0,
                "readOnly": parent_record._is_readonly() if parent_record else False,
            }

        read_only = parent_record._is_readonly() if parent_record else False
        if len(self) == 1:
            line = self[0]
            return {
                "quantity": line.quantity,
                "price": line.unit_cost,
                "readOnly": read_only,
            }

        self.product_id.ensure_one()
        quantity = sum(self.mapped("quantity"))
        subtotal = sum(self.mapped("subtotal"))
        return {
            "quantity": quantity,
            "price": subtotal / quantity if quantity else self[0].unit_cost,
            "readOnly": True,
        }

    @api.constrains("quantity", "unit_cost")
    def _check_non_negative_values(self):
        for line in self:
            if line.quantity < 0:
                raise ValidationError("Quantity cannot be negative.")
            if line.unit_cost < 0:
                raise ValidationError("Unit cost cannot be negative.")

    @api.constrains("display_type", "product_id", "product_uom_id", "quantity", "unit_cost")
    def _check_display_type_values(self):
        for line in self:
            if line.display_type:
                if line.product_id or line.product_uom_id or line.quantity or line.unit_cost:
                    raise ValidationError("Display lines cannot have product, quantity or cost values.")
            elif not line.product_id or not line.product_uom_id:
                raise ValidationError("Product and unit of measure are required on product lines.")
