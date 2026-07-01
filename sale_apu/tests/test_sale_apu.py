from odoo.tests.common import TransactionCase


class TestSaleApu(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "APU Customer"})
        cls.pricelist = cls.env.ref("product.list0")
        cls.unit_uom = cls.env.ref("uom.product_uom_unit")
        cls.product = cls.env["product.template"].create(
            {
                "name": "APU Product",
                "detailed_type": "consu",
                "sale_ok": True,
                "purchase_ok": True,
                "standard_price": 42.5,
                "list_price": 100.0,
                "uom_id": cls.unit_uom.id,
                "uom_po_id": cls.unit_uom.id,
            }
        ).product_variant_id
        cls.sale_product = cls.env["product.template"].create(
            {
                "name": "Sale Product",
                "detailed_type": "consu",
                "sale_ok": True,
                "purchase_ok": True,
                "standard_price": 5.0,
                "list_price": 100.0,
                "uom_id": cls.unit_uom.id,
                "uom_po_id": cls.unit_uom.id,
            }
        ).product_variant_id

    def _create_order(self, amount=100.0):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "pricelist_id": self.pricelist.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.sale_product.id,
                            "name": self.sale_product.name,
                            "product_uom_qty": 1.0,
                            "price_unit": amount,
                        },
                    )
                ],
            }
        )
        return order

    def test_product_cost_is_copied_into_apu_line(self):
        order = self._create_order()
        line = self.env["sale.order.apu.line"].create(
            {
                "sale_order_id": order.id,
                "product_id": self.product.id,
                "quantity": 2.0,
            }
        )
        self.assertAlmostEqual(line.unit_cost, 42.5, places=2)
        self.assertEqual(line.name, self.product.display_name)
        self.assertEqual(line.product_uom_id, self.product.uom_id)

    def test_subtotal_and_totals_are_computed(self):
        order = self._create_order(amount=100.0)
        self.env["sale.order.apu.line"].create(
            {
                "sale_order_id": order.id,
                "product_id": self.product.id,
                "quantity": 2.0,
                "unit_cost": 30.0,
            }
        )
        self.assertAlmostEqual(order.apu_total, 60.0, places=2)
        self.assertAlmostEqual(order.apu_expected_profit, 40.0, places=2)
        self.assertAlmostEqual(order.apu_margin_percent, 40.0, places=2)

    def test_zero_quotation_amount_is_safe(self):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "pricelist_id": self.pricelist.id,
            }
        )
        self.env["sale.order.apu.line"].create(
            {
                "sale_order_id": order.id,
                "product_id": self.product.id,
                "quantity": 1.0,
                "unit_cost": 25.0,
            }
        )
        self.assertEqual(order.amount_untaxed, 0.0)
        self.assertAlmostEqual(order.apu_total, 25.0, places=2)
        self.assertAlmostEqual(order.apu_expected_profit, -25.0, places=2)
        self.assertEqual(order.apu_margin_percent, 0.0)

    def test_copy_duplicates_apu_lines(self):
        order = self._create_order(amount=100.0)
        original_line = self.env["sale.order.apu.line"].create(
            {
                "sale_order_id": order.id,
                "product_id": self.product.id,
                "quantity": 3.0,
                "unit_cost": 15.0,
            }
        )
        copied_order = order.copy()
        self.assertEqual(len(copied_order.apu_line_ids), 1)
        copied_line = copied_order.apu_line_ids[0]
        self.assertNotEqual(copied_line.id, original_line.id)
        self.assertEqual(copied_line.product_id, original_line.product_id)
        self.assertAlmostEqual(copied_line.quantity, original_line.quantity, places=2)
        self.assertAlmostEqual(copied_line.unit_cost, original_line.unit_cost, places=2)

    def test_historical_cost_stays_unchanged_after_product_update(self):
        order = self._create_order(amount=100.0)
        line = self.env["sale.order.apu.line"].create(
            {
                "sale_order_id": order.id,
                "product_id": self.product.id,
                "quantity": 1.0,
            }
        )
        self.product.standard_price = 99.99
        self.assertAlmostEqual(line.unit_cost, 42.5, places=2)

    def test_changing_product_refreshes_snapshot(self):
        order = self._create_order(amount=100.0)
        other_product = self.env["product.template"].create(
            {
                "name": "Other APU Product",
                "detailed_type": "consu",
                "sale_ok": True,
                "purchase_ok": True,
                "standard_price": 77.7,
                "list_price": 120.0,
                "uom_id": self.unit_uom.id,
                "uom_po_id": self.unit_uom.id,
            }
        ).product_variant_id
        line = self.env["sale.order.apu.line"].create(
            {
                "sale_order_id": order.id,
                "product_id": self.product.id,
                "quantity": 1.0,
            }
        )
        line.write({"product_id": other_product.id})
        self.assertEqual(line.product_id, other_product)
        self.assertAlmostEqual(line.unit_cost, 77.7, places=2)
        self.assertEqual(line.name, other_product.display_name)
        self.assertEqual(line.product_uom_id, other_product.uom_id)
