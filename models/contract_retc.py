from odoo import models, fields, api
from odoo.exceptions import UserError


class ContractRETC(models.Model):
    _name = 'setraco.contract.retc'
    _description = 'Revised Estimated Total Cost (RETC)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'revision_date desc'

    name = fields.Char(
        string='RETC Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('setraco.contract.retc'),
    )
    contract_id = fields.Many2one(
        'setraco.contract.agreement',
        string='Contract',
        required=True,
        tracking=True,
    )
    tender_id = fields.Many2one(
        related='contract_id.tender_id',
        string='Tender',
        store=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    revision_number = fields.Integer(
        string='Revision No.',
        default=1,
        tracking=True,
    )
    revision_date = fields.Date(
        string='Revision Date',
        default=fields.Date.today,
        required=True,
        tracking=True,
    )

    # ── Cost Figures ──────────────────────────────────────────────────────────

    original_contract_value = fields.Monetary(
        string='Original Contract Value',
        currency_field='currency_id',
        tracking=True,
    )
    original_estimated_cost = fields.Monetary(
        string='Original Estimated Cost',
        currency_field='currency_id',
        tracking=True,
    )
    previous_retc = fields.Monetary(
        string='Previous RETC',
        currency_field='currency_id',
        tracking=True,
    )
    revised_estimated_cost = fields.Monetary(
        string='Revised Estimated Total Cost',
        currency_field='currency_id',
        required=True,
        tracking=True,
    )
    cost_variance = fields.Monetary(
        string='Cost Variance',
        currency_field='currency_id',
        compute='_compute_variance',
        store=True,
    )
    variance_percentage = fields.Float(
        string='Variance (%)',
        compute='_compute_variance',
        store=True,
        digits=(5, 2),
    )

    # ── Reason & VOP ──────────────────────────────────────────────────────────

    revision_reason = fields.Selection([
        ('scope_change', 'Scope Change'),
        ('material_price', 'Volatile Material Prices'),
        ('labor_cost', 'Labor Cost Change'),
        ('unforeseen', 'Unforeseen Site Conditions'),
        ('vop', 'Variation of Price (VOP)'),
        ('design_change', 'Design Change'),
        ('other', 'Other'),
    ], string='Primary Reason', required=True, tracking=True)
    revision_detail = fields.Text(
        string='Detailed Explanation',
        tracking=True,
    )
    vop_id = fields.Many2one(
        'setraco.contract.vop',
        string='Related VOP',
        tracking=True,
    )

    # ── Approval ──────────────────────────────────────────────────────────────

    prepared_by = fields.Many2one(
        'res.users',
        string='Prepared By',
        default=lambda self: self.env.user,
        tracking=True,
    )
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By (MD)',
        tracking=True,
    )
    approval_date = fields.Date(
        string='Approval Date',
        tracking=True,
    )
    notes = fields.Html(string='Notes')
    document_ids = fields.Many2many(
        'ir.attachment',
        string='Supporting Documents',
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends('revised_estimated_cost', 'original_estimated_cost', 'previous_retc')
    def _compute_variance(self):
        for rec in self:
            base = rec.previous_retc or rec.original_estimated_cost or 0.0
            rec.cost_variance = rec.revised_estimated_cost - base
            rec.variance_percentage = (
                (rec.cost_variance / base * 100) if base else 0.0
            )

    @api.model
    def _get_next_revision_number(self, contract_id):
        last = self.search(
            [('contract_id', '=', contract_id), ('state', '=', 'approved')],
            order='revision_number desc',
            limit=1,
        )
        return (last.revision_number + 1) if last else 1

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_submit(self):
        self.ensure_one()
        self.state = 'submitted'

    def action_approve(self):
        self.ensure_one()
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Date.today(),
        })

    def action_reject(self):
        self.ensure_one()
        self.state = 'rejected'

    def action_reset_draft(self):
        self.ensure_one()
        if self.state == 'approved':
            raise UserError('An approved RETC cannot be reset to draft.')
        self.state = 'draft'