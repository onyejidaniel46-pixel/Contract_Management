# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ContractClaim(models.Model):
    """
    Interim and final claims certificates.
    Created by Project Management; circulated by Contract Dept to
    MD, Accounts, Projects, Cost Control, Tax Department.
    """
    _name = 'setraco.contract.claim'
    _description = 'Claims Certificate'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'claim_number desc'

    name = fields.Char(
        string='Certificate Reference',
        required=True, copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    claim_number = fields.Integer(
        string='Claim No.',
        required=True,
        tracking=True,
    )
    agreement_id = fields.Many2one(
        'setraco.contract.agreement',
        string='Contract',
        required=True,
        ondelete='cascade',
    )
    client_id = fields.Many2one(related='agreement_id.client_id', store=True)
    currency_id = fields.Many2one(related='agreement_id.currency_id', store=True)
    invoice_id = fields.Many2one(
        'account.move',
        string='Customer Invoice',
        copy=False,
        readonly=True,
    )

    claim_type = fields.Selection([
        ('interim', 'Interim Claim'),
        ('final',   'Final Claim'),
    ], string='Type', required=True, default='interim', tracking=True)

    state = fields.Selection([
        ('draft',       'Draft'),
        ('submitted',   'Submitted to Client'),
        ('certified',   'Certified by Client'),
        ('paid',        'Paid'),
        ('disputed',    'Disputed'),
    ], string='Status', default='draft', tracking=True, copy=False)

    # ── Period ────────────────────────────────────────────────────────────
    period_from = fields.Date(string='Period From', required=True)
    period_to   = fields.Date(string='Period To', required=True)
    date_submitted = fields.Date(string='Date Submitted', tracking=True)
    date_certified = fields.Date(string='Date Certified', tracking=True)
    date_paid      = fields.Date(string='Date Paid', tracking=True)

    # ── Amounts ───────────────────────────────────────────────────────────
    amount_claimed = fields.Monetary(
        string='Amount Claimed',
        currency_field='currency_id',
        required=True,
        tracking=True,
    )
    amount_certified = fields.Monetary(
        string='Amount Certified by Client',
        currency_field='currency_id',
        tracking=True,
    )
    amount_paid = fields.Monetary(
        string='Amount Paid',
        currency_field='currency_id',
        tracking=True,
    )
    retention_amount = fields.Monetary(
        string='Retention Withheld',
        currency_field='currency_id',
        tracking=True,
    )
    net_payable = fields.Monetary(
        string='Net Payable',
        compute='_compute_net_payable', store=True,
        currency_field='currency_id',
    )

    # ── Dry / Selling cost split ──────────────────────────────────────────
    dry_cost_this_period = fields.Monetary(
        string='Dry Cost (This Period)',
        currency_field='currency_id',
        help='Direct costs incurred on site this period.',
    )
    selling_cost_this_period = fields.Monetary(
        string='Selling / Indirect Cost (This Period)',
        currency_field='currency_id',
        help='Indirect costs linked to this certificate.',
    )

    # ── Circulation List ──────────────────────────────────────────────────
    circulated_to_md = fields.Boolean(string='Circulated to MD')
    circulated_to_accounts = fields.Boolean(string='Circulated to Accounts')
    circulated_to_projects = fields.Boolean(string='Circulated to Projects')
    circulated_to_cost_control = fields.Boolean(string='Circulated to Cost Control')
    circulated_to_tax = fields.Boolean(string='Circulated to Tax Dept')

    # ── Overdue Alert ─────────────────────────────────────────────────────
    payment_due_date = fields.Date(
        string='Payment Due Date',
        tracking=True,
    )
    is_overdue = fields.Boolean(
        string='Payment Overdue',
        compute='_compute_overdue', store=True,
    )
    days_overdue = fields.Integer(
        string='Days Overdue',
        compute='_compute_overdue', store=True,
    )

    notes = fields.Text(string='Notes / Description of Works')

    @api.depends('amount_certified', 'retention_amount')
    def _compute_net_payable(self):
        for rec in self:
            rec.net_payable = (rec.amount_certified or 0) - (rec.retention_amount or 0)

    @api.depends('state', 'payment_due_date')
    def _compute_overdue(self):
        today = fields.Date.today()
        for rec in self:
            if rec.state in ('submitted', 'certified') and rec.payment_due_date:
                delta = (today - rec.payment_due_date).days
                rec.is_overdue = delta > 0
                rec.days_overdue = max(0, delta)
            else:
                rec.is_overdue = False
                rec.days_overdue = 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'setraco.contract.claim'
                ) or _('New')
        return super().create(vals_list)

    # ── Workflow ──────────────────────────────────────────────────────────
    def action_submit_to_client(self):
        self.write({
            'state': 'submitted',
            'date_submitted': fields.Date.today(),
        })
        self.message_post(body=_('Certificate submitted to client for approval.'))
        self._circulate_certificate()

    def action_mark_certified(self):
        self.ensure_one()
        if not self.amount_certified:
            raise UserError(_('Please enter the certified amount before confirming.'))
        
        # Create Customer Invoice in draft status
        if not self.invoice_id:
            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': self.client_id.id,
                'currency_id': self.currency_id.id,
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': [(0, 0, {
                    'name': _('Certified Claim %s for Contract %s (Period: %s - %s)') % (
                        self.name, self.agreement_id.name, self.period_from, self.period_to
                    ),
                    'quantity': 1.0,
                    'price_unit': self.net_payable,
                })],
            }
            invoice = self.env['account.move'].create(invoice_vals)
            self.invoice_id = invoice.id
            chatter_msg = _('Client certified amount: %s. Draft Customer Invoice created.') % self.amount_certified
        else:
            chatter_msg = _('Client certified amount: %s.') % self.amount_certified

        self.write({'state': 'certified', 'date_certified': fields.Date.today()})
        self.message_post(body=chatter_msg)

    def action_view_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_('No customer invoice linked to this claim certificate.'))
        return {
            'name': _('Customer Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_mark_paid(self):
        self.write({'state': 'paid', 'date_paid': fields.Date.today(),
                    'amount_paid': self.amount_certified})
        self.message_post(body=_('Payment received from client.'))
        # Notify Contract Department
        self.agreement_id.tender_id.message_post(
            body=_('Payment received for claim certificate %s.') % self.name
        )

    def action_mark_disputed(self):
        self.write({'state': 'disputed'})

    def _circulate_certificate(self):
        """Mark all circulation flags as sent and post chatter message."""
        self.write({
            'circulated_to_md': True,
            'circulated_to_accounts': True,
            'circulated_to_projects': True,
            'circulated_to_cost_control': True,
            'circulated_to_tax': True,
        })
        self.message_post(
            body=_('Certificate circulated to: MD, Accounts, Projects, '
                'Cost Control, Tax Department.')
        )