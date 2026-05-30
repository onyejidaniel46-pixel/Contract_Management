# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ContractVOP(models.Model):
    """
    Variation of Price (VOP) — adjustments to contract price due to
    changes in material costs, labour, or other inputs during execution.
    """
    _name = 'setraco.contract.vop'
    _description = 'Variation of Price (VOP)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_raised desc'

    name = fields.Char(
        string='VOP Reference',
        required=True, copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    agreement_id = fields.Many2one(
        'setraco.contract.agreement',
        string='Contract',
        required=True,
        ondelete='cascade',
    )
    currency_id = fields.Many2one(related='agreement_id.currency_id', store=True)

    state = fields.Selection([
        ('draft',     'Draft'),
        ('submitted', 'Submitted to Contract Dept'),
        ('approved',  'Approved by Client'),
        ('rejected',  'Rejected'),
        ('boq_updated', 'BOQ Updated'),
    ], string='Status', default='draft', tracking=True)

    date_raised = fields.Date(string='Date Raised', default=fields.Date.today, required=True)
    date_submitted = fields.Date(string='Date Submitted to Contract Dept', tracking=True)
    date_client_response = fields.Date(string='Client Response Date', tracking=True)

    vop_type = fields.Selection([
        ('material_price', 'Material Price Change'),
        ('labour_rate',    'Labour Rate Change'),
        ('additional_qty', 'Additional Quantities'),
        ('scope_change',   'Scope Change'),
        ('client_delay',   'Client Delay Adjustment'),
        ('inflation',      'Inflation / Market Conditions'),
    ], string='VOP Type', required=True, tracking=True)

    description = fields.Text(string='Description / Justification', required=True)

    # ── VOP Lines (BOQ items affected) ─────────────────────────────────────
    vop_line_ids = fields.One2many('setraco.contract.vop.line', 'vop_id', string='VOP Lines')

    original_amount = fields.Monetary(
        string='Original Contract Value',
        related='agreement_id.contract_value',
        currency_field='currency_id',
    )
    vop_amount = fields.Monetary(
        string='VOP Amount',
        compute='_compute_vop_amount', store=True,
        currency_field='currency_id',
    )
    adjusted_contract_value = fields.Monetary(
        string='Adjusted Contract Value',
        compute='_compute_vop_amount', store=True,
        currency_field='currency_id',
    )

    client_delay_days = fields.Integer(
        string='Client Delay (Days)',
        help='Number of days of client-caused delay for adjustment.',
    )
    supporting_document = fields.Binary(string='Supporting Document', attachment=True)
    supporting_document_filename = fields.Char()

    @api.depends('vop_line_ids.amount')
    def _compute_vop_amount(self):
        for rec in self:
            rec.vop_amount = sum(rec.vop_line_ids.mapped('amount'))
            rec.adjusted_contract_value = rec.original_amount + rec.vop_amount

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'setraco.contract.vop'
                ) or _('New')
        return super().create(vals_list)

    def action_submit_to_contract(self):
        self.write({'state': 'submitted', 'date_submitted': fields.Date.today()})

    def action_approve(self):
        self.write({'state': 'approved', 'date_client_response': fields.Date.today()})
        self.message_post(body=_('VOP approved by client.'))

    def action_reject(self):
        self.write({'state': 'rejected', 'date_client_response': fields.Date.today()})

    def action_update_boq(self):
        """Mark BOQ as updated, update contract agreement value, and log RETC history."""
        if self.state != 'approved':
            raise UserError(_('VOP must be approved before updating BOQ.'))
        
        self.ensure_one()
        agreement = self.agreement_id
        previous_value = agreement.contract_value

        # 1. Update the contract value and RETC on the agreement
        agreement.write({
            'contract_value': self.adjusted_contract_value,
            'retc': self.adjusted_contract_value,
        })

        # 2. Automatically generate RETC Audit Trail record
        self.env['setraco.contract.retc.history'].create({
            'agreement_id': agreement.id,
            'date': fields.Date.today(),
            'previous_retc': previous_value,
            'new_retc': self.adjusted_contract_value,
            'reason': 'vop',
            'notes': _('Adjusted automatically via approved VOP: %s') % self.name,
        })

        self.write({'state': 'boq_updated'})
        self.message_post(
            body=_('BOQ updated with VOP rates. Contract Value and RETC automatically adjusted to: %s')
            % self.adjusted_contract_value
        )


class ContractVOPLine(models.Model):
    _name = 'setraco.contract.vop.line'
    _description = 'VOP Line Item'

    vop_id = fields.Many2one('setraco.contract.vop', ondelete='cascade')
    boq_item = fields.Char(string='BOQ Item / Description', required=True)
    original_rate = fields.Monetary(string='Original Rate', currency_field='currency_id')
    new_rate = fields.Monetary(string='New Rate', currency_field='currency_id')
    quantity = fields.Float(string='Quantity', default=1.0)
    amount = fields.Monetary(
        string='Adjustment Amount',
        compute='_compute_amount', store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(related='vop_id.currency_id', store=True)

    @api.depends('new_rate', 'original_rate', 'quantity')
    def _compute_amount(self):
        for line in self:
            line.amount = (line.new_rate - line.original_rate) * line.quantity