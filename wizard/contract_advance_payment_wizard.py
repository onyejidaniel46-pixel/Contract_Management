# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ContractAdvancePaymentWizard(models.TransientModel):
    _name = 'setraco.contract.advance.payment.wizard'
    _description = 'Confirm Advance Payment Received'

    tender_id = fields.Many2one(
        'setraco.contract.tender',
        string='Tender',
        required=True,
    )
    amount = fields.Monetary(
        string='Advance Payment Amount',
        currency_field='currency_id',
        required=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='tender_id.currency_id',
        readonly=True,
    )
    payment_date = fields.Date(
        string='Payment Date',
        required=True,
        default=fields.Date.today,
    )
    guarantee_source = fields.Selection([
        ('accounts', 'Accounts Department'),
        ('bank', 'Bank'),
    ], string='Guarantee Source', required=True, default='accounts')
    
    notes = fields.Text(string='Notes')

    def action_confirm(self):
        self.ensure_one()
        tender = self.tender_id
        
        # Write to tender
        tender.write({
            'advance_payment_amount': self.amount,
            'advance_payment_date': self.payment_date,
            'advance_payment_received': True,
            'performance_guarantee': True,
            'performance_guarantee_source': self.guarantee_source,
        })
        
        # Log to chatter
        guarantee_label = dict(self._fields['guarantee_source'].selection).get(self.guarantee_source)
        body = _("Advance payment of %s %s received on %s.<br/>Performance Guarantee acquired via %s.<br/><strong>Notes:</strong> %s") % (
            self.amount,
            self.currency_id.name or '',
            self.payment_date,
            guarantee_label,
            self.notes or 'None'
        )
        tender.message_post(body=body)
        
        return {'type': 'ir.actions.act_window_close'}
