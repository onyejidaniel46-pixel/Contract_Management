# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ContractAgreement(models.Model):
    _name = 'setraco.contract.agreement'
    _description = 'Contract Agreement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_signed desc'

    name = fields.Char(
        string='Agreement Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    tender_id = fields.Many2one(
        'setraco.contract.tender',
        string='Source Tender',
        required=True,
        ondelete='restrict',
    )
    client_id = fields.Many2one('res.partner', string='Client', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)

    # ── Contract Details ──────────────────────────────────────────────────
    contract_value = fields.Monetary(
        string='Contract Value',
        currency_field='currency_id',
        required=True,
        tracking=True,
    )
    date_signed = fields.Date(string='Date Signed', required=True, tracking=True)
    date_commencement = fields.Date(string='Commencement Date', tracking=True)
    date_completion = fields.Date(string='Completion Date', tracking=True)
    maintenance_period_months = fields.Integer(
        string='Maintenance Period (Months)',
        default=12,
        help='Per contract terms — typically max 12 months after handover.',
    )

    state = fields.Selection([
        ('draft',          'Draft'),
        ('active',         'Active'),
        ('claims',         'In Claims'),
        ('final_cert',     'Final Certificate'),
        ('maintenance',    'Maintenance Period'),
        ('closed',         'Closed'),
    ], string='Status', default='draft', tracking=True, copy=False)

    # ── Project / Operations ──────────────────────────────────────────────
    project_id = fields.Many2one(
        'project.project',
        string='Linked Project',
        help='Project created in Project module for operations tracking.',
    )
    project_manager_id = fields.Many2one(
        'res.users',
        string='Project Manager',
        tracking=True,
    )
    site_location = fields.Char(string='Site Location', tracking=True)

    # ── RETC Tracking ─────────────────────────────────────────────────────
    retc = fields.Monetary(
        string='RETC (Revised Est. Total Cost)',
        currency_field='currency_id',
        tracking=True,
        help='Revised Estimated Total Cost — updated as conditions change.',
    )
    retc_history_ids = fields.One2many(
        'setraco.contract.retc.history',
        'agreement_id',
        string='RETC Revision History',
    )

    # ── Claims Certificates ───────────────────────────────────────────────
    claim_ids = fields.One2many(
        'setraco.contract.claim',
        'agreement_id',
        string='Claims Certificates',
    )
    claim_count = fields.Integer(compute='_compute_claim_count', string='Claims')
    total_claimed = fields.Monetary(
        string='Total Claimed',
        compute='_compute_claim_totals', store=True,
        currency_field='currency_id',
    )
    total_certified = fields.Monetary(
        string='Total Certified by Client',
        compute='_compute_claim_totals', store=True,
        currency_field='currency_id',
    )
    total_paid = fields.Monetary(
        string='Total Paid',
        compute='_compute_claim_totals', store=True,
        currency_field='currency_id',
    )
    balance_outstanding = fields.Monetary(
        string='Balance Outstanding',
        compute='_compute_claim_totals', store=True,
        currency_field='currency_id',
    )

    # ── Cost Alert Settings (per contract) ────────────────────────────────
    dry_cost_budget = fields.Monetary(
        string='Dry Cost Budget',
        currency_field='currency_id',
        help='Direct cost budget for site. Alerts fire when threshold is reached.',
    )
    dry_cost_alert_threshold = fields.Float(
        string='Alert Threshold (%)',
        default=80.0,
        help='Send alert when actual dry costs reach this % of budget.',
    )

    # ── Documents ─────────────────────────────────────────────────────────
    program_of_works = fields.Binary(string='Program of Works', attachment=True)
    program_of_works_filename = fields.Char()
    contract_document = fields.Binary(string='Signed Contract', attachment=True)
    contract_document_filename = fields.Char()

    notes = fields.Html(string='Terms & Notes')

    # ── Handover ──────────────────────────────────────────────────────────
    handover_date = fields.Date(string='Handover Date to Client', tracking=True)
    maintenance_end_date = fields.Date(
        string='Maintenance Period End',
        compute='_compute_maintenance_end', store=True,
    )

    @api.depends('handover_date', 'maintenance_period_months')
    def _compute_maintenance_end(self):
        from dateutil.relativedelta import relativedelta
        for rec in self:
            if rec.handover_date and rec.maintenance_period_months:
                rec.maintenance_end_date = (
                    rec.handover_date + relativedelta(months=rec.maintenance_period_months)
                )
            else:
                rec.maintenance_end_date = False

    @api.depends('claim_ids')
    def _compute_claim_count(self):
        for rec in self:
            rec.claim_count = len(rec.claim_ids)

    @api.depends(
        'claim_ids.amount_claimed',
        'claim_ids.amount_certified',
        'claim_ids.amount_paid',
    )
    def _compute_claim_totals(self):
        for rec in self:
            rec.total_claimed    = sum(rec.claim_ids.mapped('amount_claimed'))
            rec.total_certified  = sum(rec.claim_ids.mapped('amount_certified'))
            rec.total_paid       = sum(rec.claim_ids.mapped('amount_paid'))
            rec.balance_outstanding = rec.contract_value - rec.total_paid

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'setraco.contract.agreement'
                ) or _('New')
        return super().create(vals_list)

    def action_activate(self):
        self.write({'state': 'active'})

    def action_start_claims(self):
        self.write({'state': 'claims'})

    def action_final_certificate(self):
        self.write({'state': 'final_cert'})

    def action_start_maintenance(self):
        self.write({'state': 'maintenance', 'handover_date': fields.Date.today()})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_update_retc(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Update RETC'),
            'res_model': 'setraco.contract.retc.history',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_agreement_id': self.id},
        }

    def action_view_claims(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Claims Certificates'),
            'res_model': 'setraco.contract.claim',
            'view_mode': 'list,form',
            'domain': [('agreement_id', '=', self.id)],
            'context': {'default_agreement_id': self.id},
        }

    def _get_realtime_site_dry_costs(self):
        self.ensure_one()
        if not self.project_id or not self.project_id.analytic_account_id:
            return 0.0
        # Sum all debit lines on the analytic account (material purchases, timesheets, fleet costs)
        analytic_lines = self.env['account.analytic.line'].search([
            ('account_id', '=', self.project_id.analytic_account_id.id),
            ('amount', '<', 0.0),
        ])
        return abs(sum(analytic_lines.mapped('amount')))


class ContractRETCHistory(models.Model):
    """Audit trail for every RETC revision."""
    _name = 'setraco.contract.retc.history'
    _description = 'RETC Revision History'
    _order = 'date desc'

    agreement_id = fields.Many2one(
        'setraco.contract.agreement', string='Contract', ondelete='cascade'
    )
    date = fields.Date(string='Revision Date', default=fields.Date.today, required=True)
    previous_retc = fields.Monetary(string='Previous RETC', currency_field='currency_id')
    new_retc = fields.Monetary(string='New RETC', currency_field='currency_id', required=True)
    reason = fields.Selection([
        ('scope_change',   'Scope Change'),
        ('vop',            'Variation of Price (VOP)'),
        ('unforeseen',     'Unforeseen Conditions'),
        ('additional_work','Additional Works'),
        ('other',          'Other'),
    ], string='Reason', required=True)
    notes = fields.Text(string='Details')
    currency_id = fields.Many2one(related='agreement_id.currency_id', store=True)
    revised_by_id = fields.Many2one(
        'res.users', string='Revised By', default=lambda self: self.env.user
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.agreement_id.write({'retc': rec.new_retc})
        return records