from odoo import models, fields, api
from odoo.exceptions import UserError


class ContractLOI(models.Model):
    _name = 'setraco.contract.loi'
    _description = 'Letter of Intent'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_received desc'

    name = fields.Char(
        string='LOI Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('setraco.contract.loi'),
    )
    tender_id = fields.Many2one(
        'setraco.contract.tender',
        string='Related Tender',
        required=True,
        tracking=True,
    )
    contract_id = fields.Many2one(
        'setraco.contract.agreement',
        string='Related Contract',
        tracking=True,
    )
    client_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        tracking=True,
    )
    date_received = fields.Date(
        string='Date Received',
        required=True,
        tracking=True,
    )
    date_accepted = fields.Date(
        string='Date Accepted',
        tracking=True,
    )
    date_deadline = fields.Date(
        string='Response Deadline',
        tracking=True,
    )
    loi_amount = fields.Monetary(
        string='LOI Amount',
        currency_field='currency_id',
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    advance_payment_requested = fields.Boolean(
        string='Advance Payment Requested',
        tracking=True,
    )
    advance_payment_amount = fields.Monetary(
        string='Advance Payment Amount',
        currency_field='currency_id',
        tracking=True,
    )
    advance_payment_date = fields.Date(
        string='Advance Payment Request Date',
        tracking=True,
    )
    notes = fields.Html(
        string='Notes / Terms',
    )
    document_ids = fields.Many2many(
        'ir.attachment',
        string='Attached Documents',
    )
    state = fields.Selection([
        ('received', 'Received'),
        ('under_review', 'Under Review'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('advance_requested', 'Advance Payment Requested'),
    ], string='Status', default='received', tracking=True)

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_review(self):
        self.ensure_one()
        self.state = 'under_review'

    def action_accept(self):
        self.ensure_one()
        if self.state not in ('received', 'under_review'):
            raise UserError('Only a received or under-review LOI can be accepted.')
        self.write({
            'state': 'accepted',
            'date_accepted': fields.Date.today(),
        })

    def action_reject(self):
        self.ensure_one()
        self.state = 'rejected'

    def action_request_advance_payment(self):
        self.ensure_one()
        if self.state != 'accepted':
            raise UserError('The LOI must be accepted before requesting an advance payment.')
        self.write({
            'state': 'advance_requested',
            'advance_payment_requested': True,
            'advance_payment_date': fields.Date.today(),
        })