from odoo import models, fields, api


class ContractBOQ(models.Model):
    _name = 'setraco.contract.boq'
    _description = 'Bill of Quantities (BOQ) / Bill of Engineering Material (BME)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='BOQ Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('setraco.contract.boq'),
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
    estimation_id = fields.Many2one(
        'setraco.contract.estimation',
        string='Related Estimation',
        tracking=True,
    )
    document_type = fields.Selection([
        ('boq', 'Bill of Quantities (BOQ)'),
        ('bme', 'Bill of Engineering Material (BME)'),
    ], string='Document Type', default='boq', required=True, tracking=True)
    prepared_by = fields.Many2one(
        'res.users',
        string='Prepared By',
        default=lambda self: self.env.user,
    )
    date_prepared = fields.Date(
        string='Date Prepared',
        default=fields.Date.today,
    )
    source_department = fields.Selection([
        ('procurement', 'Procurement Department'),
        ('plant', 'Plant Department'),
        ('personnel', 'Personnel Department'),
        ('cost_control', 'Cost Control Department'),
        ('operations', 'Operations Department'),
    ], string='Source Department', tracking=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    line_ids = fields.One2many(
        'setraco.contract.boq.line',
        'boq_id',
        string='BOQ Lines',
    )
    total_amount = fields.Monetary(
        string='Total Amount',
        currency_field='currency_id',
        compute='_compute_total',
        store=True,
    )
    notes = fields.Html(string='Notes')
    document_ids = fields.Many2many(
        'ir.attachment',
        string='Attached Documents',
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('approved', 'Approved'),
    ], string='Status', default='draft', tracking=True)

    @api.depends('line_ids.subtotal')
    def _compute_total(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('subtotal'))

    def action_confirm(self):
        self.state = 'confirmed'

    def action_approve(self):
        self.state = 'approved'

    def action_reset_draft(self):
        self.state = 'draft'


class ContractBOQLine(models.Model):
    _name = 'setraco.contract.boq.line'
    _description = 'BOQ Line Item'
    _order = 'sequence, id'

    boq_id = fields.Many2one(
        'setraco.contract.boq',
        string='BOQ',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(string='Seq.', default=10)
    item_type = fields.Selection([
        ('material', 'Material'),
        ('labor', 'Labor'),
        ('equipment', 'Equipment'),
        ('overhead', 'Overhead / Operational'),
        ('subcontract', 'Subcontract'),
    ], string='Type', required=True, default='material')
    description = fields.Char(
        string='Description',
        required=True,
    )
    specification = fields.Text(
        string='Specification / Detail',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product (optional)',
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
    )
    quantity = fields.Float(
        string='Quantity',
        required=True,
        default=1.0,
        digits=(12, 3),
    )
    unit_price = fields.Float(
        string='Unit Rate',
        required=True,
        digits=(12, 2),
    )
    subtotal = fields.Monetary(
        string='Subtotal',
        currency_field='currency_id',
        compute='_compute_subtotal',
        store=True,
    )
    currency_id = fields.Many2one(
        related='boq_id.currency_id',
        store=True,
    )
    notes = fields.Char(string='Remarks')

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price