# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ContractMdApprovalWizard(models.TransientModel):
    _name = 'setraco.contract.md.approval.wizard'
    _description = 'MD Approval Decision Wizard'

    tender_id = fields.Many2one(
        'setraco.contract.tender',
        string='Tender',
        required=True,
    )
    action = fields.Selection([
        ('approve', 'Approve & Submit'),
        ('reject', 'Reject / Cancel'),
        ('changes', 'Request Changes'),
    ], string='Decision', required=True, default='approve')

    notes = fields.Text(string='Notes / Instructions')

    def action_confirm(self):
        self.ensure_one()
        tender = self.tender_id

        if self.action == 'approve':
            tender.write({
                'state': 'submitted',
            })
            # Log approval message
            tender.message_post(
                body=_("MD Approved. Tender formally submitted to client.<br/><strong>Notes:</strong> %s") % (self.notes or 'None')
            )
        elif self.action == 'reject':
            tender.write({
                'state': 'cancelled',
                'cancellation_reason': self.notes,
            })
            tender.message_post(
                body=_("MD Rejected / Cancelled the Tender.<br/><strong>Reason:</strong> %s") % (self.notes or 'None')
            )
        elif self.action == 'changes':
            # Request changes: reset to estimation stage
            tender.write({
                'state': 'estimation',
            })
            tender.message_post(
                body=_("MD requested changes / revision.<br/><strong>Instructions:</strong> %s") % (self.notes or 'None')
            )

        return {'type': 'ir.actions.act_window_close'}
