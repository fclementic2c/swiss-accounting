# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.base.models.res_bank import sanitize_account_number
from odoo.addons.l10n_ch.tests.test_swissqr import TestSwissQR, CH_IBAN, QR_IBAN
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestSwissQRExtra(TestSwissQR):

    def generate_swissqr_url(self, invoice, qr_iban_acc_number=False):
        """ Prints the given invoice and tests that a Swiss QR generation is triggered. """
        self.assertTrue(
            invoice.can_generate_qr_bill(), 'A Swiss QR can be generated'
        )
        self.assertTrue(invoice.invoice_payment_ref)
        if qr_iban_acc_number:
            iban = invoice.invoice_partner_bank_id.sanitized_acc_number
        else:
            iban = sanitize_account_number(invoice.invoice_partner_bank_id.l10n_ch_qr_iban)

        payload = (
            "SPC%0A"
            "0200%0A"
            "1%0A"
            "{iban}%0A"
            "K%0A"
            "YourCompany%0A"
            "Route+de+Berne+88%0A"
            "2000+Neuch%C3%A2tel%0A"
            "%0A%0A"
            "CH%0A"
            "%0A%0A%0A%0A%0A%0A%0A"
            "42.00%0A"
            "CHF%0A"
            "K%0A"
            "Partner%0A"
            "Route+de+Berne+41%0A"
            "1000+Lausanne%0A"
            "%0A%0A"
            "CH%0A"
            "QRR%0A"
            "{struct_ref}%0A"
            "{unstr_msg}%0A"
            "EPD"
        ).format(
            iban=iban,
            struct_ref=invoice.invoice_payment_ref or '',
            unstr_msg=(invoice.ref or invoice.name or invoice.number).replace('/', '%2F'),
        )

        expected_url = ("/report/barcode/?type=QR&value={}"
                        "&width=256&height=256&quiet=1").format(payload)

        url = invoice.invoice_partner_bank_id.build_swiss_code_url(
            invoice.amount_residual,
            invoice.currency_id.name,
            None,
            invoice.partner_id,
            None,
            invoice.invoice_payment_ref,
            invoice.ref or invoice.name,
        )
        self.assertEqual(url, expected_url)

    def test_swissQR_ch_qriban(self):
        # We have non QR-IBAN account number but we have a valid QR-IBAN
        # set in l10n_ch_qr_iban, so we are still good to print a QR Bill.
        iban_account = self.create_account(CH_IBAN)
        iban_account.l10n_ch_qr_iban = QR_IBAN
        self.invoice1.invoice_partner_bank_id = iban_account
        self.invoice1.post()
        self.generate_swissqr_url(self.invoice1)

    def test_swissQR_qriban_acc_number(self):
        # We have QR-IBAN account number and we have a valid QR-IBAN set in
        # l10n_ch_qr_iban as well, so we should print a QR Bill with account number.
        QR_IBAN1 = 'CH44 3199 9123 0008 8901 2'
        qriban_account = self.create_account(QR_IBAN1)
        qriban_account.l10n_ch_qr_iban = QR_IBAN
        self.invoice1.invoice_partner_bank_id = qriban_account
        self.invoice1.post()
        self.generate_swissqr_url(self.invoice1, qr_iban_acc_number=True)
