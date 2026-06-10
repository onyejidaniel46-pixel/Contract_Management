from odoo import models, fields, api
from odoo.exceptions import UserError


class ContractAdvancePayment(models.Model):
    _name = 'setraco.contract.advance.payment'
    _description = 'Advance Payment & Performance Guarantee' 
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'payment_date desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('setraco.contract.advance.payment'),
    )
    contract_id = fields.Many2one(
        'setraco.contract.agreement',
        string='Contract',
        required=True,
        tracking=True,
    )
    loi_id = fields.Many2one(
        'setraco.contract.loi',
        string='Letter of Intent',
        tracking=True,
    )
    client_id = fields.Many2one(
        related='contract_id.client_id',
        string='Client',
        store=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )

    # ── Advance Payment ───────────────────────────────────────────────────────

    advance_amount = fields.Monetary(
        string='Advance Payment Amount',
        currency_field='currency_id',
        required=True,
        tracking=True,
    )
    payment_date = fields.Date(
        string='Payment Received Date',
        tracking=True,
    )
    payment_reference = fields.Char(
        string='Payment Reference / Cheque No.',
        tracking=True,
    )
    bank_name = fields.Char(
        string='Bank Name',
    )
    payment_received = fields.Boolean(
        string='Payment Received',
        default=False,
        tracking=True,
    )

    # ── Performance Guarantee ─────────────────────────────────────────────────

    guarantee_required = fields.Boolean(
        string='Performance Guarantee Required',
        default=True,
        tracking=True,
    )
    guarantee_type = fields.Selection([
        ('bank', 'Bank Guarantee'),
        ('internal', 'Internal (Accounts Dept)'),
        ('insurance', 'Insurance Bond'),
    ], string='Guarantee Source', tracking=True)
    guarantee_amount = fields.Monetary(
        string='Guarantee Amount',
        currency_field='currency_id',
        tracking=True,
    )
    guarantee_reference = fields.Char(
        string='Guarantee Reference No.',
        tracking=True,
    )
    guarantee_issuer = fields.Char(
        string='Issued By (Bank / Department)',
        tracking=True,
    )
    guarantee_start_date = fields.Date(
        string='Guarantee Start Date',
        tracking=True,
    )
    guarantee_expiry_date = fields.Date(
        string='Guarantee Expiry Date',
        tracking=True,
    )
    guarantee_obtained = fields.Boolean(
        string='Guarantee Obtained',
        default=False,
        tracking=True,
    )

    notes = fields.Html(string='Additional Notes')
    document_ids = fields.Many2many(
        'ir.attachment',
        string='Supporting Documents',
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('awaiting_payment', 'Awaiting Payment'),
        ('payment_received', 'Payment Received'),
        ('guarantee_pending', 'Guarantee Pending'),
        ('guarantee_obtained', 'Guarantee Obtained'),
        ('complete', 'Complete'),
    ], string='Status', default='draft', tracking=True)

    # ── Computed ──────────────────────────────────────────────────────────────

    guarantee_expired = fields.Boolean(
        string='Guarantee Expired',
        compute='_compute_guarantee_expired',
        store=True,
    )

    @api.depends('guarantee_expiry_date')
    def _compute_guarantee_expired(self):
        today = fields.Date.today()
        for rec in self:
            rec.guarantee_expired = (
                bool(rec.guarantee_expiry_date) and rec.guarantee_expiry_date < today
            )

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_confirm_payment(self):
        self.ensure_one()
        self.write({
            'payment_received': True,
            'payment_date': fields.Date.today(),
            'state': 'payment_received' if not self.guarantee_required else 'guarantee_pending',
        })

    def action_confirm_guarantee(self):
        self.ensure_one()
        if not self.payment_received:
            raise UserError('Advance payment must be received before confirming the guarantee.')
        self.write({
            'guarantee_obtained': True,
            'state': 'guarantee_obtained',
        })

    def action_mark_complete(self):
        self.ensure_one()
        if self.guarantee_required and not self.guarantee_obtained:
            raise UserError('Performance guarantee has not been obtained yet.')
        self.state = 'complete'