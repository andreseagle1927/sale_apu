from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaleOrderApuLine(models.Model):
    _name = "sale.order.apu.line"
    _description = "Sale Order APU Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Quotation",
        required=True,
        ondelete="cascade",
        index=True,
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
        required=True,
        check_company=True,
        index=True,
    )
    name = fields.Char(string="Description", required=True)
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit of Measure",
        required=True,
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
        ("quantity_non_negative", "CHECK(quantity >= 0)", "Quantity cannot be negative."),
        ("unit_cost_non_negative", "CHECK(unit_cost >= 0)", "Unit cost cannot be negative."),
    ]

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if not line.product_id:
                continue
            line._apply_product_snapshot()

    @api.depends("quantity", "unit_cost")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_cost

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            product_id = vals.get("product_id")
            if product_id:
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
        result = super().write(vals)
        if "product_id" in vals or "sale_order_id" in vals:
            for line in self:
                if line.product_id and line.sale_order_id:
                    line._apply_product_snapshot()
        return result

    def _apply_product_snapshot(self):
        self.ensure_one()
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

    @api.constrains("quantity", "unit_cost")
    def _check_non_negative_values(self):
        for line in self:
            if line.quantity < 0:
                raise ValidationError("Quantity cannot be negative.")
            if line.unit_cost < 0:
                raise ValidationError("Unit cost cannot be negative.")
