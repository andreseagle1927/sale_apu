from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _apu_mirror_is_eligible(self):
        self.ensure_one()
        return not self.is_downpayment

    def _apu_mirror_get_values(self, refresh_cost=False):
        self.ensure_one()
        if self.display_type:
            return {
                "sale_order_id": self.order_id.id,
                "source_order_line_id": self.id,
                "sequence": self.sequence,
                "display_type": self.display_type,
                "name": self.name or "",
            }

        if not self._apu_mirror_is_eligible() or not self.product_id:
            return False

        values = {
            "sale_order_id": self.order_id.id,
            "source_order_line_id": self.id,
            "sequence": self.sequence,
            "product_id": self.product_id.id,
            "name": self.name or self.product_id.display_name,
            "product_uom_id": self.product_uom.id,
            "quantity": self.product_uom_qty,
        }
        if refresh_cost:
            values["unit_cost"] = self.order_id._get_apu_product_cost(self.product_id)
        return values

    def _apu_sync_mirror_line(self, refresh_cost=False):
        ApuLine = self.env["sale.order.apu.line"]
        for line in self:
            if not line.order_id:
                continue

            mirrored_line = ApuLine.search([("source_order_line_id", "=", line.id)], limit=1)
            if mirrored_line and mirrored_line.display_type != line.display_type:
                mirrored_line.unlink()
                mirrored_line = False
            values = line._apu_mirror_get_values(refresh_cost=refresh_cost or not mirrored_line)
            if not values:
                if mirrored_line:
                    mirrored_line.unlink()
                continue

            if mirrored_line:
                mirrored_line.write(values)
            else:
                ApuLine.create(values)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get("skip_apu_mirror"):
            lines._apu_sync_mirror_line(refresh_cost=True)
        return lines

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get("skip_apu_mirror"):
            refresh_cost = "product_id" in vals or "order_id" in vals
            self._apu_sync_mirror_line(refresh_cost=refresh_cost)
        return result
