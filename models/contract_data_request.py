from odoo import models, fields, api
from odoo.exceptions import UserError


class ContractDataRequest(models.Model):
    _name = 'setraco.contract.data.request'
    _description = 'Inter-Departmental Data Request for Tender Preparation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc'

    name = fields.Char(
        string='Request Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('setraco.contract.data.request'),
    )

    # ── Links ─────────────────────────────────────────────────────────────────

    tender_id = fields.Many2one(
        'setraco.contract.tender',
        string='Tender',
        required=True,
        tracking=True,
        ondelete='restrict',
    )
    prequalification_id = fields.Many2one(
        'setraco.contract.prequalification',
        string='Pre-Qualification / Tender Doc',
        tracking=True,
        ondelete='set null',
    )

    # ── Department & Data Type ────────────────────────────────────────────────

    department = fields.Selection([
        ('cost_control', 'Cost Control Department'),
        ('procurement', 'Procurement Department'),
        ('plant', 'Plant Department'),
        ('personnel', 'Personnel Department'),
        ('operations', 'Operations Department'),
    ], string='Department', required=True, tracking=True)

    data_type = fields.Selection([
        ('cost_data', 'Cost Data'),
        ('market_price', 'Market Prices (BOQ)'),
        ('equipment_rate', 'Equipment Rates'),
        ('labor_rate', 'Labour Rates'),
        ('operational_cost', 'Operational Costs'),
        ('other', 'Other'),
    ], string='Data Type Required', required=True, tracking=True)

    description = fields.Text(
        string='Request Details',
        help='Describe exactly what data is needed, including scope, period, or specific items.',
        required=True,
    )

    # ── Dates ─────────────────────────────────────────────────────────────────

    request_date = fields.Date(
        string='Date Requested',
        default=fields.Date.today,
        required=True,
        tracking=True,
    )
    response_deadline = fields.Date(
        string='Response Deadline',
        required=True,
        tracking=True,
    )
    response_date = fields.Date(
        string='Date Response Received',
        tracking=True,
    )

    # ── Responsibility ────────────────────────────────────────────────────────

    requested_by = fields.Many2one(
        'res.users',
        string='Requested By',
        default=lambda self: self.env.user,
        tracking=True,
    )
    department_contact = fields.Many2one(
        'res.users',
        string='Department Contact / Respondent',
        tracking=True,
    )

    # ── Response Data ─────────────────────────────────────────────────────────

    response_summary = fields.Text(
        string='Response Summary',
        help='Brief summary of data provided by the department.',
        tracking=True,
    )
    response_value = fields.Float(
        string='Response Value (if applicable)',
        digits=(16, 2),
        tracking=True,
        help='Use for single-figure responses e.g. a labour rate or equipment rate.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    response_value_currency = fields.Monetary(
        string='Response Value (Currency)',
        currency_field='currency_id',
        tracking=True,
        help='Use for monetary responses such as cost data or market prices.',
    )
    response_document_ids = fields.Many2many(
        'ir.attachment',
        'data_request_attachment_rel',
        'request_id',
        'attachment_id',
        string='Response Documents',
        help='Attach spreadsheets, rate sheets, or any documents from the department.',
    )

    # ── Status ────────────────────────────────────────────────────────────────

    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent to Department'),
        ('acknowledged', 'Acknowledged by Department'),
        ('received', 'Response Received'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_is_overdue',
        store=True,
    )
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Urgent'),
        ('2', 'Critical'),
    ], string='Priority', default='0')

    notes = fields.Html(string='Internal Notes')

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends('response_deadline', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_overdue = (
                bool(rec.response_deadline)
                and rec.response_deadline < today
                and rec.state not in ('received', 'cancelled')
            )

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_send(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError('Only a draft request can be sent.')
        if not self.department_contact:
            raise UserError('Please assign a Department Contact before sending.')
        self.state = 'sent'
        # Optionally trigger email notification here via mail template
        self._notify_department()

    def action_acknowledge(self):
        self.ensure_one()
        if self.state != 'sent':
            raise UserError('Only a sent request can be acknowledged.')
        self.state = 'acknowledged'

    def action_mark_received(self):
        self.ensure_one()
        if self.state not in ('sent', 'acknowledged'):
            raise UserError('The request must be sent or acknowledged before marking as received.')
        if not self.response_summary and not self.response_document_ids:
            raise UserError(
                'Please enter a response summary or attach response documents before marking as received.'
            )
        self.write({
            'state': 'received',
            'response_date': fields.Date.today(),
        })

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'received':
            raise UserError('A received data request cannot be cancelled.')
        self.state = 'cancelled'

    def action_reset_draft(self):
        self.ensure_one()
        if self.state in ('received',):
            raise UserError('A received request cannot be reset to draft.')
        self.state = 'draft'

    def _notify_department(self):
        """
        Post a message to the chatter to notify the assigned department contact.
        Extend this method to trigger a mail template for email notification.
        """
        self.ensure_one()
        if self.department_contact:
            self.message_post(
                body=(
                    f"Data request sent to <strong>{self.department_contact.name}</strong> "
                    f"({dict(self._fields['department'].selection).get(self.department, '')}).<br/>"
                    f"<strong>Response required by:</strong> {self.response_deadline}"
                ),
                partner_ids=[self.department_contact.partner_id.id],
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )


class ContractDataRequestBatch(models.Model):
    """
    Convenience model to create multiple data requests at once
    for a single tender, one per department.
    """
    _name = 'setraco.contract.data.request.batch'
    _description = 'Batch Data Request for Tender'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char(
        string='Batch Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'setraco.contract.data.request.batch'
        ),
    )
    tender_id = fields.Many2one(
        'setraco.contract.tender',
        string='Tender',
        required=True,
        tracking=True,
    )
    prequalification_id = fields.Many2one(
        'setraco.contract.prequalification',
        string='Pre-Qualification Doc',
        tracking=True,
    )
    response_deadline = fields.Date(
        string='Global Response Deadline',
        required=True,
        tracking=True,
    )
    data_request_ids = fields.One2many(
        'setraco.contract.data.request',
        'prequalification_id',
        string='Generated Requests',
        readonly=True,
    )
    total_requests = fields.Integer(
        string='Total Requests',
        compute='_compute_totals',
    )
    received_count = fields.Integer(
        string='Received',
        compute='_compute_totals',
    )
    pending_count = fields.Integer(
        string='Pending',
        compute='_compute_totals',
    )

    # Departments to include in this batch
    include_cost_control = fields.Boolean(string='Cost Control', default=True)
    include_procurement = fields.Boolean(string='Procurement', default=True)
    include_plant = fields.Boolean(string='Plant', default=True)
    include_personnel = fields.Boolean(string='Personnel', default=True)
    include_operations = fields.Boolean(string='Operations', default=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('dispatched', 'Dispatched'),
        ('complete', 'All Responses Received'),
    ], string='Status', default='draft', tracking=True)

    @api.depends('data_request_ids', 'data_request_ids.state')
    def _compute_totals(self):
        for rec in self:
            reqs = rec.data_request_ids
            rec.total_requests = len(reqs)
            rec.received_count = len(reqs.filtered(lambda r: r.state == 'received'))
            rec.pending_count = rec.total_requests - rec.received_count

    def action_dispatch_all(self):
        """Generate one data request per selected department and send them."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError('Requests have already been dispatched.')

        dept_map = [
            ('cost_control', 'cost_data', 'Cost data required for tender estimation.'),
            ('procurement', 'market_price', 'Market prices (BOQ) required for tender costing.'),
            ('plant', 'equipment_rate', 'Current equipment rates required for tender.'),
            ('personnel', 'labor_rate', 'Current labour rates required for tender.'),
            ('operations', 'operational_cost', 'Operational cost data required for tender.'),
        ]
        Request = self.env['setraco.contract.data.request']
        for dept_key, data_type, desc in dept_map:
            if getattr(self, f'include_{dept_key}'):
                req = Request.create({
                    'tender_id': self.tender_id.id,
                    'prequalification_id': self.prequalification_id.id,
                    'department': dept_key,
                    'data_type': data_type,
                    'description': desc,
                    'request_date': fields.Date.today(),
                    'response_deadline': self.response_deadline,
                    'requested_by': self.env.user.id,
                })
                req.action_send()

        self.state = 'dispatched'

    def action_check_completion(self):
        self.ensure_one()
        if self.pending_count == 0 and self.total_requests > 0:
            self.state = 'complete'
        else:
            raise UserError(
                f'{self.pending_count} department response(s) still pending.'
            )