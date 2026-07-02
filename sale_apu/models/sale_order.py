from collections import defaultdict

from odoo import api, fields, models, _
from odoo.http import request


class SaleOrder(models.Model):
    _inherit = "sale.order"

    apu_line_ids = fields.One2many(
        comodel_name="sale.order.apu.line",
        inverse_name="sale_order_id",
        string="APU Lines",
        copy=False,
        groups="sale_apu.group_apu_view_costs,sales_team.group_sale_manager",
    )
    apu_total = fields.Monetary(
        string="Total APU",
        currency_field="currency_id",
        compute="_compute_apu_summary",
        store=True,
        readonly=True,
        groups="sale_apu.group_apu_view_costs,sales_team.group_sale_manager",
    )
    apu_expected_profit = fields.Monetary(
        string="Expected Profit",
        currency_field="currency_id",
        compute="_compute_apu_summary",
        store=True,
        readonly=True,
        groups="sale_apu.group_apu_view_costs,sales_team.group_sale_manager",
    )
    apu_margin_percent = fields.Float(
        string="Margin (%)",
        compute="_compute_apu_summary",
        store=True,
        readonly=True,
        digits=(16, 2),
        groups="sale_apu.group_apu_view_costs,sales_team.group_sale_manager",
    )

    @api.depends("amount_untaxed", "apu_line_ids", "apu_line_ids.display_type", "apu_line_ids.subtotal")
    def _compute_apu_summary(self):
        for order in self:
            apu_total = sum(order.apu_line_ids.filtered(lambda line: not line.display_type).mapped("subtotal"))
            order.apu_total = apu_total
            order.apu_expected_profit = order.amount_untaxed - apu_total
            if order.amount_untaxed:
                order.apu_margin_percent = (order.apu_expected_profit / order.amount_untaxed) * 100.0
            else:
                order.apu_margin_percent = 0.0

    def action_add_apu_from_catalog(self):
        self.ensure_one()
        action = self.with_context(child_field="apu_line_ids", apu_catalog=True).action_add_from_catalog()
        action["name"] = _("APU Catalog")
        return action

    def _get_apu_product_cost(self, product):
        self.ensure_one()
        product = product.with_company(self.company_id).sudo()
        price_date = self.date_order.date() if self.date_order else fields.Date.context_today(self)
        return self.company_id.currency_id._convert(
            product.standard_price,
            self.currency_id,
            self.company_id,
            price_date,
        )

    def _apu_catalog_active(self):
        return bool(self.env.context.get("apu_catalog"))

    def _get_product_catalog_order_data(self, products, **kwargs):
        if self._apu_catalog_active():
            return {
                product.id: {
                    "productType": product.type,
                    "price": self._get_apu_product_cost(product),
                    "readOnly": self._is_readonly(),
                }
                for product in products
            }

        pricelist = self.pricelist_id._get_products_price(
            quantity=1.0,
            products=products,
            currency=self.currency_id,
            date=self.date_order,
            **kwargs,
        )
        res = super()._get_product_catalog_order_data(products, **kwargs)
        for product in products:
            res[product.id]["price"] = pricelist.get(product.id)
            if product.sale_line_warn != "no-message" and product.sale_line_warn_msg:
                res[product.id]["warning"] = product.sale_line_warn_msg
            if product.sale_line_warn == "block":
                res[product.id]["readOnly"] = True
        return res

    def _get_product_catalog_record_lines(self, product_ids, **kwargs):
        if self._apu_catalog_active():
            grouped_lines = defaultdict(lambda: self.env["sale.order.apu.line"])
            for line in self.apu_line_ids:
                if line.display_type or line.product_id.id not in product_ids:
                    continue
                grouped_lines[line.product_id] |= line
            return grouped_lines

        grouped_lines = defaultdict(lambda: self.env["sale.order.line"])
        for line in self.order_line:
            if line.display_type or line.product_id.id not in product_ids:
                continue
            grouped_lines[line.product_id] |= line
        return grouped_lines

    def _update_order_line_info(self, product_id, quantity, **kwargs):
        if self._apu_catalog_active():
            try:
                request.update_context(catalog_skip_tracking=True)
            except Exception:
                pass
            apu_line = self.apu_line_ids.filtered(lambda line: not line.display_type and line.product_id.id == product_id)[:1]
            if apu_line:
                if quantity != 0:
                    apu_line.quantity = quantity
                elif self.state in ["draft", "sent"]:
                    price = self._get_apu_product_cost(apu_line.product_id)
                    apu_line.unlink()
                    return price
                else:
                    apu_line.quantity = 0
            elif quantity > 0:
                apu_line = self.env["sale.order.apu.line"].create(
                    {
                        "sale_order_id": self.id,
                        "product_id": product_id,
                        "quantity": quantity,
                        "sequence": ((self.apu_line_ids and self.apu_line_ids[-1].sequence + 1) or 10),
                    }
                )
            else:
                return self._get_apu_product_cost(self.env["product.product"].browse(product_id))

            return apu_line.unit_cost

        return super()._update_order_line_info(product_id, quantity, **kwargs)

    def copy(self, default=None):
        self.ensure_one()
        new_order = super().copy(default=default)
        for line in self.apu_line_ids.filtered(lambda apu_line: not apu_line.source_order_line_id):
            line.copy(default={"sale_order_id": new_order.id})
        return new_order
