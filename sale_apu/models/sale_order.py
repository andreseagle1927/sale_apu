from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    apu_line_ids = fields.One2many(
        comodel_name="sale.order.apu.line",
        inverse_name="sale_order_id",
        string="APU Lines",
        copy=False,
        groups="sale_apu.group_apu_view_costs,sale.group_sale_manager",
    )
    apu_total = fields.Monetary(
        string="Total APU",
        currency_field="currency_id",
        compute="_compute_apu_summary",
        store=True,
        readonly=True,
        groups="sale_apu.group_apu_view_costs,sale.group_sale_manager",
    )
    apu_expected_profit = fields.Monetary(
        string="Expected Profit",
        currency_field="currency_id",
        compute="_compute_apu_summary",
        store=True,
        readonly=True,
        groups="sale_apu.group_apu_view_costs,sale.group_sale_manager",
    )
    apu_margin_percent = fields.Float(
        string="Margin (%)",
        compute="_compute_apu_summary",
        store=True,
        readonly=True,
        digits=(16, 2),
        groups="sale_apu.group_apu_view_costs,sale.group_sale_manager",
    )

    @api.depends("amount_untaxed", "apu_line_ids", "apu_line_ids.subtotal")
    def _compute_apu_summary(self):
        for order in self:
            apu_total = sum(order.apu_line_ids.mapped("subtotal"))
            order.apu_total = apu_total
            order.apu_expected_profit = order.amount_untaxed - apu_total
            if order.amount_untaxed:
                order.apu_margin_percent = (order.apu_expected_profit / order.amount_untaxed) * 100.0
            else:
                order.apu_margin_percent = 0.0

    def copy(self, default=None):
        self.ensure_one()
        new_order = super().copy(default=default)
        for line in self.apu_line_ids:
            line.copy(default={"sale_order_id": new_order.id})
        return new_order
