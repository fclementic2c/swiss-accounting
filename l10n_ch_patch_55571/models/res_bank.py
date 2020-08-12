# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
import werkzeug.urls

from odoo import api, models, _



class ResPartnerBank(models.Model):
    """Patch by OVERWRITTING methods"""
    _inherit = 'res.partner.bank'

    def _prepare_swiss_code_url_vals(self, amount, currency_name, debtor_partner, reference_type, reference, comment):
        creditor_addr_1, creditor_addr_2 = self._get_partner_address_lines(self.partner_id)
        debtor_addr_1, debtor_addr_2 = self._get_partner_address_lines(debtor_partner)

        return [
            'SPC',                                                # QR Type
            '0200',                                               # Version
            '1',                                                  # Coding Type
            self.sanitized_acc_number,                            # IBAN
            'K',                                                  # Creditor Address Type
            (self.acc_holder_name or self.partner_id.name)[:70],  # Creditor Name
            creditor_addr_1,                                      # Creditor Address Line 1
            creditor_addr_2,                                      # Creditor Address Line 2
            '',                                                   # Creditor Postal Code (empty, since we're using combined addres elements)
            '',                                                   # Creditor Town (empty, since we're using combined addres elements)
            self.partner_id.country_id.code,                      # Creditor Country
            '',                                                   # Ultimate Creditor Address Type
            '',                                                   # Name
            '',                                                   # Ultimate Creditor Address Line 1
            '',                                                   # Ultimate Creditor Address Line 2
            '',                                                   # Ultimate Creditor Postal Code
            '',                                                   # Ultimate Creditor Town
            '',                                                   # Ultimate Creditor Country
            '{:.2f}'.format(amount),                              # Amount
            currency_name,                                        # Currency
            'K',                                                  # Ultimate Debtor Address Type
            debtor_partner.name[:70],                             # Ultimate Debtor Name
            debtor_addr_1,                                        # Ultimate Debtor Address Line 1
            debtor_addr_2,                                        # Ultimate Debtor Address Line 2
            '',                                                   # Ultimate Debtor Postal Code (not to be provided for address type K)
            '',                                                   # Ultimate Debtor Postal City (not to be provided for address type K)
            debtor_partner.country_id.code,                       # Ultimate Debtor Postal Country
            reference_type,                                       # Reference Type
            reference,                                            # Reference
            comment,                                              # Unstructured Message
            'EPD',                                                # Mandatory trailer part
        ]

    @api.model
    def build_swiss_code_url(self, amount, currency_name, not_used_anymore_1, debtor_partner, not_used_anymore_2, structured_communication, free_communication):
        comment = ""
        if free_communication:
            comment = (free_communication[:137] + '...') if len(free_communication) > 140 else free_communication

        # Compute reference type (empty by default, only mandatory for QR-IBAN,
        # and must then be 27 characters-long, with mod10r check digit as the 27th one,
        # just like ISR number for invoices)
        reference_type = 'NON'
        reference = ''
        if self._is_qr_iban():
            # _check_for_qr_code_errors ensures we can't have a QR-IBAN without a QR-reference here
            reference_type = 'QRR'
            reference = structured_communication

        qr_code_vals = self._prepare_swiss_code_url_vals(amount, currency_name, debtor_partner, reference_type, reference, comment)

        # use quiet to remove blank around the QR and make it easier to place it
        return '/report/barcode/?type=%s&value=%s&width=%s&height=%s&quiet=1' % ('QR', werkzeug.urls.url_quote_plus('\n'.join(qr_code_vals)), 256, 256)

    def _validate_qr_iban(self, iban):
        if not iban or len(iban) < 9:
            return False
        iid_start_index = 4
        iid_end_index = 8
        iid = iban[iid_start_index : iid_end_index+1]
        return re.match('\d+', iid) \
               and 30000 <= int(iid) <= 31999 # Those values for iid are reserved for QR-IBANs only

    def _is_qr_iban(self):
        """ Tells whether or not this bank account has a QR-IBAN account number.
        QR-IBANs are specific identifiers used in Switzerland as references in
        QR-codes. They are formed like regular IBANs, but are actually something
        different.
        """
        # for conveniance when invoice.invoice_partner_bank_id, could be replaced
        # by a computed field
        if not self:
            return False

        self.ensure_one()

        return self.acc_type == 'iban' \
               and self._validate_qr_iban(self.sanitized_acc_number)
