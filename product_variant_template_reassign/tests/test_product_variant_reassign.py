# Copyright 2024 Tecnativa - David Vidal
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import Command
from odoo.tests import Form, TransactionCase

TEST_IMAGE = (
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    b"/wcAAgAB/UTeG8kAAAAASUVORK5CYII="
)


class ProductVariantReassignCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.att_color = cls.env["product.attribute"].create({"name": "Color (test)"})
        cls.att_size = cls.env["product.attribute"].create({"name": "Size (test)"})
        cls.att_origin = cls.env["product.attribute"].create(
            {"name": "Origin (test)", "create_variant": "no_variant"}
        )
        cls.att_color_blue = cls.env["product.attribute.value"].create(
            {"name": "Blue", "attribute_id": cls.att_color.id}
        )
        cls.att_color_red = cls.env["product.attribute.value"].create(
            {"name": "Red", "attribute_id": cls.att_color.id}
        )
        cls.att_color_green = cls.env["product.attribute.value"].create(
            {"name": "Green", "attribute_id": cls.att_color.id}
        )
        cls.att_sice_xxl = cls.env["product.attribute.value"].create(
            {"name": "XXL", "attribute_id": cls.att_size.id}
        )
        cls.att_origin_nepal = cls.env["product.attribute.value"].create(
            {"name": "Nepal", "attribute_id": cls.att_origin.id}
        )
        cls.color_scarf = cls.env["product.template"].create(
            {
                "name": "Test color_scarf",
                "list_price": 25.0,
                "attribute_line_ids": [
                    Command.create(
                        {
                            "attribute_id": cls.att_color.id,
                            "value_ids": [
                                Command.set(
                                    [cls.att_color_blue.id, cls.att_color_red.id]
                                ),
                            ],
                        }
                    ),
                    Command.create(
                        {
                            "attribute_id": cls.att_origin.id,
                            "value_ids": [
                                Command.set([cls.att_origin_nepal.id]),
                            ],
                        }
                    ),
                ],
            }
        )
        cls.green_scarf = cls.env["product.template"].create(
            {
                "name": "Test color_scarf",
                "default_code": "TST-GREEN",
                "list_price": 30,
                "standard_price": 15,
                "barcode": "123456789012",
                "image_1920": TEST_IMAGE,
                "attribute_line_ids": [
                    Command.create(
                        {
                            "attribute_id": cls.att_size.id,
                            "value_ids": [
                                Command.set([cls.att_sice_xxl.id]),
                            ],
                        }
                    ),
                    Command.create(
                        {
                            "attribute_id": cls.att_origin.id,
                            "value_ids": [
                                Command.set([cls.att_origin_nepal.id]),
                            ],
                        }
                    ),
                ],
            }
        )

    def test_reassign_product(self):
        existing_color_scarves = self.color_scarf.product_variant_ids
        wiz_form = Form(
            self.env["reassign.variant"].with_context(active_id=self.green_scarf.id)
        )
        self.assertTrue(
            self.color_scarf in wiz_form.allowed_target_product_template_ids
        )
        wiz_form.target_product_template_id = self.color_scarf
        self.assertTrue(self.att_color_green in wiz_form.allowed_attribute_value_ids)
        self.assertFalse(self.att_color_red in wiz_form.allowed_attribute_value_ids)
        wiz_form.attribute_value_ids.add(self.att_color_green)
        wiz = wiz_form.save()
        wiz.reassign()
        new_color_scarve = self.color_scarf.product_variant_ids - existing_color_scarves
        self.assertEqual(
            new_color_scarve.product_template_attribute_value_ids.product_attribute_value_id,
            self.att_color_green,
        )
        self.assertEqual(new_color_scarve.default_code, "TST-GREEN")
        self.assertAlmostEqual(new_color_scarve.list_price, 30)
        self.assertAlmostEqual(new_color_scarve.standard_price, 15)
        self.assertEqual(new_color_scarve.barcode, "123456789012")
        self.assertEqual(new_color_scarve.image_variant_1920, TEST_IMAGE)
        self.assertFalse(bool(self.green_scarf.exists()))
        self.assertTrue(
            len(
                self.color_scarf.attribute_line_ids.filtered(
                    lambda x: x.attribute_id == self.att_origin
                )
            )
            == 1
        )

    def test_reassign_product_with_archived_value(self):
        """The only active variant can still hold an archived attribute value: the
        user removed the value from the template once the variant had history, so
        it was archived, and then reactivated it by hand. Its combination isn't the
        empty one the template has without attribute lines anymore."""
        att_size_s = self.env["product.attribute.value"].create(
            {"name": "S", "attribute_id": self.att_size.id}
        )
        blue_scarf = self.env["product.template"].create(
            {
                "name": "Test blue scarf",
                "default_code": "TST-BLUE",
                "barcode": "123456789029",
                "attribute_line_ids": [
                    Command.create(
                        {
                            "attribute_id": self.att_size.id,
                            "value_ids": [Command.set([self.att_sice_xxl.id])],
                        }
                    ),
                ],
            }
        )
        blue_scarf_xxl = blue_scarf.product_variant_id
        partner = self.env["res.partner"].create({"name": "Test customer"})
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [Command.create({"product_id": blue_scarf_xxl.id})],
            }
        )
        size_line = blue_scarf.attribute_line_ids
        size_line.value_ids += att_size_s
        size_line.value_ids -= self.att_sice_xxl
        self.assertFalse(blue_scarf_xxl.active)
        (blue_scarf.product_variant_ids - blue_scarf_xxl).action_archive()
        blue_scarf_xxl.action_unarchive()
        self.assertEqual(blue_scarf.product_variant_ids, blue_scarf_xxl)
        existing_color_scarves = self.color_scarf.product_variant_ids
        wiz_form = Form(
            self.env["reassign.variant"].with_context(active_id=blue_scarf.id)
        )
        wiz_form.target_product_template_id = self.color_scarf
        wiz_form.attribute_value_ids.add(self.att_color_green)
        wiz_form.save().reassign()
        new_color_scarf = self.color_scarf.product_variant_ids - existing_color_scarves
        self.assertEqual(
            new_color_scarf.product_template_attribute_value_ids.product_attribute_value_id,
            self.att_color_green,
        )
        self.assertEqual(new_color_scarf.default_code, "TST-BLUE")
        self.assertEqual(new_color_scarf.barcode, "123456789029")
        self.assertEqual(order.order_line.product_id, new_color_scarf)
        self.assertFalse(blue_scarf_xxl.exists())
        self.assertFalse(blue_scarf.exists())
