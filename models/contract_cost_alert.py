# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ContractCostAlert(models.Model):
    """
    Cost alert engine — tracks actual costs against budget thresholds
    and fires notifications when limits are approached or exceeded.
    Covers both dry costs (direct/site) and selling costs (indirect).
    """
    _name = 'setraco.contract.cost.alert'
    _description = 'Contract Cost Alert'
    _inherit = ['mail.thread']
    _order = 'date_triggered desc'

    name = fields.Char(string='Alert Reference', required=True, copy=False,
                    readonly=True, default=lambda self: _('New'))
    agreement_id = fields.Many2one(
        'setraco.contract.agreement', string='Contract', required=True
    )
    currency_id = fields.Many2one(related='agreement_id.currency_id', store=True)

    alert_type = fields.Selection([
        ('dry_cost',     'Dry Cost Threshold'),
        ('selling_cost', 'Selling Cost Threshold'),
        ('payment_overdue', 'Payment Overdue'),
        ('retc_exceeded',  'RETC Exceeded'),
    ], string='Alert Type', required=True, tracking=True)

    threshold_percent = fields.Float(string='Threshold (%)', default=80.0)
    budget_amount = fields.Monetary(string='Budget Amount', currency_field='currency_id')
    actual_amount = fields.Monetary(string='Actual Amount', currency_field='currency_id')
    usage_percent = fields.Float(
        string='Usage (%)',
        compute='_compute_usage', store=True,
    )

    state = fields.Selection([
        ('active',     'Active'),
        ('triggered',  'Triggered'),
        ('resolved',   'Resolved'),
        ('dismissed',  'Dismissed'),
    ], string='Status', default='active', tracking=True)

    date_triggered = fields.Datetime(string='Date Triggered', tracking=True)
    resolved_by_id = fields.Many2one('res.users', string='Resolved By')
    resolution_notes = fields.Text(string='Resolution Notes')

    @api.depends('actual_amount', 'budget_amount')
    def _compute_usage(self):
        for rec in self:
            if rec.budget_amount:
                rec.usage_percent = (rec.actual_amount / rec.budget_amount) * 100
            else:
                rec.usage_percent = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'setraco.contract.cost.alert'
                ) or _('New')
        return super().create(vals_list)

    def action_resolve(self):
        self.write({
            'state': 'resolved',
            'resolved_by_id': self.env.user.id,
        })

    def action_dismiss(self):
        self.write({'state': 'dismissed'})

    @api.model
    def _cron_check_cost_alerts(self):
        """
        Scheduled action — runs daily.
        Checks all active contracts for cost threshold breaches.
        """
        agreements = self.env['setraco.contract.agreement'].search([
            ('state', 'in', ('active', 'claims')),
        ])
        for agreement in agreements:
            if not agreement.dry_cost_budget:
                continue
            # Fetch actual dry cost (prefer analytic accounting, fallback to manual claim certificates)
            if agreement.project_id and agreement.project_id.analytic_account_id:
                total_dry = agreement._get_realtime_site_dry_costs()
            else:
                total_dry = sum(agreement.claim_ids.mapped('dry_cost_this_period'))
            
            usage_pct = (total_dry / agreement.dry_cost_budget * 100
                        if agreement.dry_cost_budget else 0)

            if usage_pct >= agreement.dry_cost_alert_threshold:
                # Avoid duplicate active alerts
                existing = self.search([
                    ('agreement_id', '=', agreement.id),
                    ('alert_type', '=', 'dry_cost'),
                    ('state', '=', 'triggered'),
                ])
                if not existing:
                    alert = self.create({
                        'agreement_id': agreement.id,
                        'alert_type': 'dry_cost',
                        'threshold_percent': agreement.dry_cost_alert_threshold,
                        'budget_amount': agreement.dry_cost_budget,
                        'actual_amount': total_dry,
                        'state': 'triggered',
                        'date_triggered': fields.Datetime.now(),
                    })
                    # Post on the contract chatter
                    agreement.message_post(
                        body=_(
                            '⚠️ Cost Alert: Dry cost has reached %(pct).1f%% '
                            'of budget (threshold: %(threshold).0f%%). '
                            'Alert reference: %(ref)s'
                        ) % {
                            'pct': usage_pct,
                            'threshold': agreement.dry_cost_alert_threshold,
                            'ref': alert.name,
                        },
                        subtype_xmlid='mail.mt_note',
                        partner_ids=agreement.project_manager_id.partner_id.ids,
                    )

        # Check payment overdue on claims
        overdue_claims = self.env['setraco.contract.claim'].search([
            ('is_overdue', '=', True),
            ('state', 'in', ('submitted', 'certified')),
        ])
        for claim in overdue_claims:
            existing = self.search([
                ('agreement_id', '=', claim.agreement_id.id),
                ('alert_type', '=', 'payment_overdue'),
                ('state', '=', 'triggered'),
            ])
            if not existing:
                self.create({
                    'agreement_id': claim.agreement_id.id,
                    'alert_type': 'payment_overdue',
                    'actual_amount': claim.amount_certified,
                    'state': 'triggered',
                    'date_triggered': fields.Datetime.now(),
                })