# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from odoo import models, api, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_split_str
from odoo.tools.misc import mod10r

l10n_ch_ISR_ID_NUM_LENGTH = 6


class AccountMove(models.Model):
    _inherit = 'account.move'

    """patch by OVERWRITE"""

    def _get_isrb_id_number(self):
        """Hook to fix the lack of proper field for ISR-B Customer ID"""
        # FIXME drop support of using l10n_ch_postal for this purpose
        # replace l10n_ch_postal to not mix it ISR-B customer ID as it
        # forbid the following validations on l10n_ch_postal
        # number for Vendor bank accounts:
        # - validation of format xx-yyyyy-c
        # - validation of checksum
        # This is patched in l10n_ch_isrb module
        self.ensure_one()
        partner_bank = self.invoice_partner_bank_id
        return partner_bank.l10n_ch_postal or ''

    @api.depends('name', 'invoice_partner_bank_id.l10n_ch_postal')
    def _compute_l10n_ch_isr_number(self):
        """ The ISR reference number is 27 characters long.

        To generate the ISR reference, the we use the invoice sequence number,
        removing each of its non-digit characters, and pad the unused spaces on
        the left of this number with zeros.
        The last digit is a checksum (mod10r).

        ISR (Postfinance)

        The reference is free but for the last
        digit which is a checksum.
        If shorter than 27 digits, it is filled with zeros on the left.

        e.g.

            120000000000234478943216899
            \________________________/|
                     1                2
            (1) 12000000000023447894321689 | reference
            (2) 9: control digit for identification number and reference

        ISR-B (Indirect through a bank, requires a customer ID)

        In case of ISR-B The firsts digits (usually 6), contain the customer ID
        at the Bank of this ISR's issuer.
        The rest (usually 20 digits) is reserved for the reference plus the
        control digit.
        If the [customer ID] + [the reference] + [the control digit] is shorter
        than 27 digits, it is filled with zeros between the customer ID till
        the start of the reference.

        e.g.

            150001123456789012345678901
            \____/\__________________/|
               1           2          3
            (1) 150001 | id number of the customer (size may vary)
            (2) 12345678901234567890 | reference
            (3) 1: control digit for identification number and reference
        """
        for record in self:
            if record.name and record.l10n_ch_isr_subscription:
                id_number = record._get_isrb_id_number()
                if id_number:
                    id_number = id_number.zfill(l10n_ch_ISR_ID_NUM_LENGTH)
                invoice_ref = re.sub('[^\d]', '', record.name)
                # keep only the last digits if it exceed boundaries
                full_len = len(id_number) + len(invoice_ref)
                extra = full_len - 26
                if extra > 0:
                    invoice_ref = invoice_ref[extra:]
                internal_ref = invoice_ref.zfill(26 - len(id_number))
                record.l10n_ch_isr_number = mod10r(id_number + internal_ref)
            else:
                record.l10n_ch_isr_number = False

    def _get_l10n_ch_isr_optical_amount(self):
        """Prepare amount string for ISR optical line"""
        self.ensure_one()
        currency_code = None
        if self.currency_id.name == 'CHF':
            currency_code = '01'
        elif self.currency_id.name == 'EUR':
            currency_code = '03'
        units, cents = float_split_str(self.amount_residual, 2)
        amount_to_display = units + cents
        amount_ref = amount_to_display.zfill(10)
        optical_amount = currency_code + amount_ref
        optical_amount = mod10r(optical_amount)
        return optical_amount

    @api.depends(
        'currency_id.name', 'amount_residual', 'name',
        'invoice_partner_bank_id.l10n_ch_isr_subscription_eur',
        'invoice_partner_bank_id.l10n_ch_isr_subscription_chf')
    def _compute_l10n_ch_isr_optical_line(self):
        """ Compute the optical line to print on the bottom of the ISR.

        This line is read by an OCR.
        It's format is:

            amount>reference+ creditor>

        Where:

           - amount: currency and invoice amount
           - reference: ISR structured reference number
                - in case of ISR-B contains the Customer ID number
                - it can also contains a partner reference (of the debitor)
           - creditor: Subscription number of the creditor

        An optical line can have the 2 following formats:

        ISR (Postfinance)

            0100003949753>120000000000234478943216899+ 010001628>
            |/\________/| \________________________/|  \_______/
            1     2     3          4                5      6

            (1) 01 | currency
            (2) 0000394975 | amount 3949.75
            (3) 4 | control digit for amount
            (5) 12000000000023447894321689 | reference
            (6) 9: control digit for identification number and reference
            (7) 010001628: subscription number (01-162-8)

        ISR-B (Indirect through a bank, requires a customer ID)

            0100000494004>150001123456789012345678901+ 010234567>
            |/\________/| \____/\__________________/|  \_______/
            1     2     3    4           5          6      7

            (1) 01 | currency
            (2) 0000049400 | amount 494.00
            (3) 4 | control digit for amount
            (4) 150001 | id number of the customer (size may vary, usually 6 chars)
            (5) 12345678901234567890 | reference
            (6) 1: control digit for identification number and reference
            (7) 010234567: subscription number (01-23456-7)
        """
        for record in self:
            record.l10n_ch_isr_optical_line = ''
            if record.l10n_ch_isr_number and record.l10n_ch_isr_subscription and record.currency_id.name:
                # Final assembly
                # (the space after the '+' is no typo, it stands in the specs.)
                record.l10n_ch_isr_optical_line = '{amount}>{reference}+ {creditor}>'.format(
                    amount=record._get_l10n_ch_isr_optical_amount(),
                    reference=record.l10n_ch_isr_number,
                    creditor=record.l10n_ch_isr_subscription,
                )

    def isr_print(self):
        """ Triggered by the 'Print ISR' button.
        """
        self.ensure_one()
        if self.l10n_ch_isr_valid:
            self.l10n_ch_isr_sent = True
            return self.env.ref('l10n_ch.l10n_ch_isr_report').report_action(self)
        else:
            errors = []
            if not self.invoice_partner_bank_id:
                errors.append(_("- Invoice's 'Bank Account' is empty. You need to create or select a valid ISR account"))
            elif not self.l10n_ch_isr_subscription:
                errors.append(_("- No ISR Subscription number is set on you company bank account. Please fill it in."))
            if self.type != "out_invoice":
                errors.append(_("- You can only print Customer ISR."))
            if self.l10n_ch_currency_name not in ['EUR', 'CHF']:
                errors.append(_("- Currency must be CHF or EUR."))
            if not self.name:
                errors.append(_("- The invoice is missing a name."))
            if not errors:
                # l10n_ch_isr_valid mismatch
                raise NotImplementedError()

            raise ValidationError(
                _("You cannot generate an ISR yet.\n"
                  "Here is what is blocking:\n"
                  "{}").format(errors))
