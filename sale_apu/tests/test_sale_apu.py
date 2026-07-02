from odoo.tests.common import TransactionCase


class TestSaleApu(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "APU Customer"})
        cls.pricelist = cls.env["product.pricelist"].create(
            {
                "name": "APU Test Pricelist",
                "currency_id": cls.env.company.currency_id.id,
            }
        )
        cls.unit_uom = cls.env.ref("uom.product_uom_unit")
        cls.product = cls.env["product.template"].create(
            {
                "name": "APU Product",
                "type": "consu",
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
                "type": "consu",
                "sale_ok": True,
                "purchase_ok": True,
                "standard_price": 0.0,
                "list_price": 100.0,
                "uom_id": cls.unit_uom.id,
                "uom_po_id": cls.unit_uom.id,
            }
        ).product_variant_id

    def _create_order(self, amount=100.0, product=None):
        product = product or self.sale_product
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "pricelist_id": self.pricelist.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": product.name,
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

    def test_display_lines_do_not_affect_apu_totals(self):
        order = self._create_order(amount=100.0)
        section = self.env["sale.order.apu.line"].create(
            {
                "sale_order_id": order.id,
                "display_type": "line_section",
                "name": "Section A",
            }
        )
        note = self.env["sale.order.apu.line"].create(
            {
                "sale_order_id": order.id,
                "display_type": "line_note",
                "name": "Note A",
            }
        )
        product_line = self.env["sale.order.apu.line"].create(
            {
                "sale_order_id": order.id,
                "product_id": self.product.id,
                "quantity": 2.0,
                "unit_cost": 12.5,
            }
        )
        self.assertEqual(section.subtotal, 0.0)
        self.assertEqual(note.subtotal, 0.0)
        self.assertAlmostEqual(product_line.subtotal, 25.0, places=2)
        self.assertAlmostEqual(order.apu_total, 25.0, places=2)
        self.assertAlmostEqual(order.apu_expected_profit, 75.0, places=2)
        self.assertAlmostEqual(order.apu_margin_percent, 75.0, places=2)

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
        original_section = self.env["sale.order.apu.line"].create(
            {
                "sale_order_id": order.id,
                "display_type": "line_section",
                "name": "Section A",
            }
        )
        original_note = self.env["sale.order.apu.line"].create(
            {
                "sale_order_id": order.id,
                "display_type": "line_note",
                "name": "Note A",
            }
        )
        original_line = self.env["sale.order.apu.line"].create(
            {
                "sale_order_id": order.id,
                "product_id": self.product.id,
                "quantity": 3.0,
                "unit_cost": 15.0,
            }
        )
        copied_order = order.copy()
        self.assertEqual(len(copied_order.apu_line_ids), 4)
        copied_section = copied_order.apu_line_ids.filtered(lambda line: line.display_type == "line_section")
        copied_note = copied_order.apu_line_ids.filtered(lambda line: line.display_type == "line_note")
        copied_product_line = copied_order.apu_line_ids.filtered(lambda line: not line.display_type and not line.source_order_line_id)
        copied_mirrored_line = copied_order.apu_line_ids.filtered(lambda line: line.source_order_line_id)
        self.assertEqual(len(copied_section), 1)
        self.assertEqual(len(copied_note), 1)
        self.assertEqual(len(copied_product_line), 1)
        self.assertEqual(len(copied_mirrored_line), 1)
        self.assertEqual(copied_section.name, original_section.name)
        self.assertEqual(copied_note.name, original_note.name)
        copied_line = copied_product_line[0]
        self.assertNotEqual(copied_line.id, original_line.id)
        self.assertEqual(copied_line.product_id, original_line.product_id)
        self.assertAlmostEqual(copied_line.quantity, original_line.quantity, places=2)
        self.assertAlmostEqual(copied_line.unit_cost, original_line.unit_cost, places=2)

    def test_sale_order_lines_mirror_into_apu_lines(self):
        order = self._create_order(amount=100.0, product=self.product)
        order_line = order.order_line[:1]
        mirrored_line = order.apu_line_ids.filtered(lambda line: line.source_order_line_id.id == order_line.id)
        self.assertEqual(len(mirrored_line), 1)
        self.assertEqual(mirrored_line.product_id, order_line.product_id)
        self.assertEqual(mirrored_line.product_uom_id, order_line.product_uom)
        self.assertEqual(mirrored_line.name, order_line.name)
        self.assertAlmostEqual(mirrored_line.quantity, order_line.product_uom_qty, places=2)
        self.assertAlmostEqual(mirrored_line.unit_cost, 42.5, places=2)

    def test_sale_order_line_updates_refresh_mirrored_apu_line(self):
        order = self._create_order(amount=100.0, product=self.product)
        order_line = order.order_line[:1]
        mirrored_line = order.apu_line_ids.filtered(lambda line: line.source_order_line_id.id == order_line.id)
        other_product = self.env["product.template"].create(
            {
                "name": "Mirror Update Product",
                "type": "consu",
                "sale_ok": True,
                "purchase_ok": True,
                "standard_price": 77.7,
                "list_price": 120.0,
                "uom_id": self.unit_uom.id,
                "uom_po_id": self.unit_uom.id,
            }
        ).product_variant_id

        order_line.write({"product_uom_qty": 3.0})
        self.assertAlmostEqual(mirrored_line.quantity, 3.0, places=2)
        self.assertAlmostEqual(mirrored_line.unit_cost, 42.5, places=2)

        order_line.write({"product_id": other_product.id, "product_uom_qty": 2.0})
        self.assertEqual(mirrored_line.product_id, other_product)
        self.assertAlmostEqual(mirrored_line.quantity, 2.0, places=2)
        self.assertAlmostEqual(mirrored_line.unit_cost, 77.7, places=2)

        order_line.unlink()
        self.assertFalse(mirrored_line.exists())

    def test_sale_order_line_sections_and_notes_mirror_into_apu(self):
        order = self._create_order(amount=100.0)
        section = self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "display_type": "line_section",
                "name": "Section A",
            }
        )
        note = self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "display_type": "line_note",
                "name": "Note A",
            }
        )
        mirrored_section = order.apu_line_ids.filtered(lambda line: line.source_order_line_id.id == section.id)
        mirrored_note = order.apu_line_ids.filtered(lambda line: line.source_order_line_id.id == note.id)
        self.assertEqual(len(mirrored_section), 1)
        self.assertEqual(len(mirrored_note), 1)
        self.assertEqual(mirrored_section.display_type, "line_section")
        self.assertEqual(mirrored_note.display_type, "line_note")
        self.assertEqual(mirrored_section.name, "Section A")
        self.assertEqual(mirrored_note.name, "Note A")

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
                "type": "consu",
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

    def test_apu_catalog_flow_uses_internal_cost(self):
        order = self._create_order(amount=100.0)
        proxy_action = self.env["sale.order.apu.line"].with_context(order_id=order.id).action_add_from_catalog()
        self.assertEqual(proxy_action["name"], "APU Catalog")
        self.assertTrue(proxy_action["context"]["apu_catalog"])

        action = order.action_add_apu_from_catalog()
        self.assertEqual(action["name"], "APU Catalog")
        self.assertTrue(action["context"]["apu_catalog"])

        price = order.with_context(apu_catalog=True)._update_order_line_info(self.product.id, 4.0)
        self.assertAlmostEqual(price, 42.5, places=2)
        line = order.apu_line_ids.filtered(lambda apu_line: apu_line.product_id == self.product)
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.quantity, 4.0, places=2)
        self.assertAlmostEqual(line.unit_cost, 42.5, places=2)
        self.assertAlmostEqual(line.subtotal, 170.0, places=2)

        price = order.with_context(apu_catalog=True)._update_order_line_info(self.product.id, 2.0)
        self.assertAlmostEqual(price, 42.5, places=2)
        line = order.apu_line_ids.filtered(lambda apu_line: apu_line.product_id == self.product)
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.quantity, 2.0, places=2)
