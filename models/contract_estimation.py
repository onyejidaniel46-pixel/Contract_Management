# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ContractEstimation(models.Model):
    _name = 'setraco.contract.estimation'
    _description = 'Contract Estimation / Tender Pricing'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Estimation Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    tender_id = fields.Many2one(
        'setraco.contract.tender',
        string='Tender',
        required=True,
        ondelete='cascade',
    )
    client_id = fields.Many2one('res.partner', string='Client', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    state = fields.Selection([
        ('draft',    'Draft'),
        ('reviewed', 'Reviewed'),
        ('approved', 'MD Approved'),
    ], default='draft', string='Status', tracking=True)

    # ── BOQ Lines ─────────────────────────────────────────────────────────
    boq_line_ids = fields.One2many(
        'setraco.contract.estimation.boq',
        'estimation_id',
        string='Bill of Quantities (BOQ)',
    )
    # ── Labour Lines ──────────────────────────────────────────────────────
    labour_line_ids = fields.One2many(
        'setraco.contract.estimation.labour',
        'estimation_id',
        string='Labour Costs',
    )
    # ── Equipment Lines ───────────────────────────────────────────────────
    equipment_line_ids = fields.One2many(
        'setraco.contract.estimation.equipment',
        'estimation_id',
        string='Equipment / Plant Rates',
    )
    # ── Operational Lines ─────────────────────────────────────────────────
    operational_line_ids = fields.One2many(
        'setraco.contract.estimation.operational',
        'estimation_id',
        string='Operational / Indirect Costs',
    )

    # ── Computed Totals ───────────────────────────────────────────────────
    total_boq = fields.Monetary(
        string='Total BOQ',
        compute='_compute_totals', store=True,
        currency_field='currency_id',
    )
    total_labour = fields.Monetary(
        string='Total Labour',
        compute='_compute_totals', store=True,
        currency_field='currency_id',
    )
    total_equipment = fields.Monetary(
        string='Total Equipment',
        compute='_compute_totals', store=True,
        currency_field='currency_id',
    )
    total_operational = fields.Monetary(
        string='Total Operational',
        compute='_compute_totals', store=True,
        currency_field='currency_id',
    )
    total_dry_cost = fields.Monetary(
        string='Total Dry Cost (Direct)',
        compute='_compute_totals', store=True,
        currency_field='currency_id',
        help='Direct costs allocated to site: BOQ + Labour + Equipment',
    )
    total_selling_cost = fields.Monetary(
        string='Total Selling Cost (Indirect)',
        compute='_compute_totals', store=True,
        currency_field='currency_id',
        help='Indirect costs linked to claims certificates',
    )
    grand_total = fields.Monetary(
        string='Grand Total (RETC)',
        compute='_compute_totals', store=True,
        currency_field='currency_id',
        help='Revised Estimated Total Cost',
    )

    # ── Markup / Margin ───────────────────────────────────────────────────
    markup_percent = fields.Float(string='Markup (%)', default=15.0)
    tender_price = fields.Monetary(
        string='Tender Price (Submitted)',
        compute='_compute_tender_price', store=True,
        currency_field='currency_id',
    )

    notes = fields.Html(string='Estimation Notes')

    @api.depends(
        'boq_line_ids.subtotal',
        'labour_line_ids.subtotal',
        'equipment_line_ids.subtotal',
        'operational_line_ids.subtotal',
    )
    def _compute_totals(self):
        for rec in self:
            rec.total_boq = sum(rec.boq_line_ids.mapped('subtotal'))
            rec.total_labour = sum(rec.labour_line_ids.mapped('subtotal'))
            rec.total_equipment = sum(rec.equipment_line_ids.mapped('subtotal'))
            rec.total_operational = sum(rec.operational_line_ids.mapped('subtotal'))
            rec.total_dry_cost = rec.total_boq + rec.total_labour + rec.total_equipment
            rec.total_selling_cost = rec.total_operational
            rec.grand_total = rec.total_dry_cost + rec.total_selling_cost

    @api.depends('grand_total', 'markup_percent')
    def _compute_tender_price(self):
        for rec in self:
            rec.tender_price = rec.grand_total * (1 + rec.markup_percent / 100)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'setraco.contract.estimation'
                ) or _('New')
        return super().create(vals_list)

    def action_submit_for_md(self):
        self.write({'state': 'reviewed'})

    def action_md_approve(self):
        self.write({'state': 'approved'})
        self.tender_id.write({'state': 'md_review'})


# ── BOQ Line ──────────────────────────────────────────────────────────────────
class ContractEstimationBOQ(models.Model):
    _name = 'setraco.contract.estimation.boq'
    _description = 'BOQ Line'
    _order = 'sequence, id'

    estimation_id = fields.Many2one('setraco.contract.estimation', ondelete='cascade')
    sequence = fields.Integer(default=10)
    item_code = fields.Char(string='Item Code')
    description = fields.Char(string='Description', required=True)
    unit = fields.Selection([
        ('m',    'Metre (m)'),
        ('m2',   'Square Metre (m²)'),
        ('m3',   'Cubic Metre (m³)'),
        ('kg',   'Kilogram (kg)'),
        ('ton',  'Tonne (t)'),
        ('nos',  'Number (nos)'),
        ('ls',   'Lump Sum'),
        ('hr',   'Hour'),
        ('day',  'Day'),
    ], string='Unit', required=True, default='m3')
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    unit_rate = fields.Monetary(
        string='Unit Rate',
        currency_field='currency_id',
        required=True,
    )
    subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_subtotal', store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='estimation_id.currency_id', store=True
    )
    source = fields.Selection([
        ('procurement', 'Procurement (Market Price)'),
        ('plant',       'Plant Department'),
        ('personnel',   'Personnel Department'),
        ('cost_control','Cost Control'),
    ], string='Data Source')

    @api.depends('quantity', 'unit_rate')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_rate


# ── Labour Line ───────────────────────────────────────────────────────────────
class ContractEstimationLabour(models.Model):
    _name = 'setraco.contract.estimation.labour'
    _description = 'Labour Cost Line'

    estimation_id = fields.Many2one('setraco.contract.estimation', ondelete='cascade')
    role = fields.Char(string='Role / Trade', required=True)
    grade = fields.Selection([
        ('unskilled', 'Unskilled Worker'),
        ('skilled',   'Skilled Worker'),
        ('foreman',   'Foreman'),
        ('supervisor','Supervisor'),
        ('engineer',  'Engineer'),
    ], string='Grade', required=True, default='skilled')
    quantity = fields.Float(string='No. of Workers', default=1.0)
    daily_rate = fields.Monetary(string='Daily Rate', currency_field='currency_id')
    duration_days = fields.Float(string='Duration (Days)')
    subtotal = fields.Monetary(
        compute='_compute_subtotal', store=True, currency_field='currency_id'
    )
    currency_id = fields.Many2one(related='estimation_id.currency_id', store=True)

    @api.depends('quantity', 'daily_rate', 'duration_days')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.daily_rate * line.duration_days


# ── Equipment Line ────────────────────────────────────────────────────────────
class ContractEstimationEquipment(models.Model):
    _name = 'setraco.contract.estimation.equipment'
    _description = 'Equipment / Plant Rate Line'

    estimation_id = fields.Many2one('setraco.contract.estimation', ondelete='cascade')
    equipment_type = fields.Char(string='Equipment Type', required=True)
    quantity = fields.Float(string='Units', default=1.0)
    daily_rate = fields.Monetary(string='Daily Rate', currency_field='currency_id')
    duration_days = fields.Float(string='Duration (Days)')
    subtotal = fields.Monetary(
        compute='_compute_subtotal', store=True, currency_field='currency_id'
    )
    currency_id = fields.Many2one(related='estimation_id.currency_id', store=True)

    @api.depends('quantity', 'daily_rate', 'duration_days')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.daily_rate * line.duration_days


# ── Operational / Indirect Costs ──────────────────────────────────────────────
class ContractEstimationOperational(models.Model):
    _name = 'setraco.contract.estimation.operational'
    _description = 'Operational / Indirect Cost Line'

    estimation_id = fields.Many2one('setraco.contract.estimation', ondelete='cascade')
    description = fields.Char(string='Cost Item', required=True)
    cost_category = fields.Selection([
        ('admin',       'Administration'),
        ('transport',   'Transportation'),
        ('insurance',   'Insurance'),
        ('community',   'Community / Social'),
        ('contingency', 'Contingency'),
        ('other',       'Other'),
    ], string='Category', required=True, default='admin')
    amount = fields.Monetary(string='Amount', currency_field='currency_id', required=True)
    subtotal = fields.Monetary(
        compute='_compute_subtotal', store=True, currency_field='currency_id'
    )
    currency_id = fields.Many2one(related='estimation_id.currency_id', store=True)

    @api.depends('amount')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.amount