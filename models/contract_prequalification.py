from odoo import models, fields, api
from odoo.exceptions import UserError


class ContractPrequalification(models.Model):
    _name = 'setraco.contract.prequalification'
    _description = 'Pre-Qualification / Tender Document Preparation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_prepared desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('setraco.contract.prequalification'),
    )
    tender_id = fields.Many2one(
        'setraco.contract.tender',
        string='Related Tender',
        required=True,
        tracking=True,
        ondelete='restrict',
    )
    client_id = fields.Many2one(
        related='tender_id.client_id',
        string='Client',
        store=True,
    )
    document_type = fields.Selection([
        ('prequalification', 'Pre-Qualification Document'),
        ('tender', 'Tender Document'),
        ('both', 'Pre-Qualification + Tender'),
    ], string='Document Type', required=True, default='prequalification', tracking=True)

    # ── Dates ─────────────────────────────────────────────────────────────────

    date_prepared = fields.Date(
        string='Date Prepared',
        default=fields.Date.today,
        required=True,
        tracking=True,
    )
    date_submitted_md = fields.Date(
        string='Date Submitted to MD',
        tracking=True,
    )
    date_md_decision = fields.Date(
        string='MD Decision Date',
        tracking=True,
    )
    date_submitted_client = fields.Date(
        string='Date Submitted to Client',
        tracking=True,
    )
    client_submission_deadline = fields.Date(
        string='Client Submission Deadline',
        tracking=True,
    )

    # ── Responsibility ────────────────────────────────────────────────────────

    prepared_by = fields.Many2one(
        'res.users',
        string='Prepared By',
        default=lambda self: self.env.user,
        tracking=True,
    )
    reviewed_by = fields.Many2one(
        'res.users',
        string='Reviewed By (Head of Contract)',
        tracking=True,
    )
    md_id = fields.Many2one(
        'res.users',
        string='Managing Director',
        tracking=True,
    )
    md_decision = fields.Selection([
        ('approved', 'Approved for Submission'),
        ('rejected', 'Rejected'),
        ('revision_required', 'Revision Required'),
    ], string='MD Decision', tracking=True)
    md_remarks = fields.Text(
        string='MD Remarks / Instructions',
        tracking=True,
    )

    # ── Estimation & Cost Links ───────────────────────────────────────────────

    estimation_id = fields.Many2one(
        'setraco.contract.estimation',
        string='Linked Estimation',
        tracking=True,
    )
    boq_id = fields.Many2one(
        'setraco.contract.boq',
        string='Linked BOQ',
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    tender_value = fields.Monetary(
        string='Tender / Bid Value',
        currency_field='currency_id',
        tracking=True,
    )

    # ── Data Collection Readiness ─────────────────────────────────────────────

    data_request_ids = fields.One2many(
        'setraco.contract.data.request',
        'prequalification_id',
        string='Dept. Data Requests',
    )
    all_data_received = fields.Boolean(
        string='All Dept. Data Received',
        compute='_compute_all_data_received',
        store=True,
    )

    # ── Document Content ──────────────────────────────────────────────────────

    scope_of_work = fields.Html(
        string='Scope of Work',
        help='Describe the work scope as it will appear in the submission.',
    )
    technical_approach = fields.Html(
        string='Technical Approach',
    )
    company_profile_included = fields.Boolean(
        string='Company Profile Included', default=False,
    )
    financial_statements_included = fields.Boolean(
        string='Financial Statements Included', default=False,
    )
    past_projects_included = fields.Boolean(
        string='Past Projects / References Included', default=False,
    )
    notes = fields.Html(string='Additional Notes')
    document_ids = fields.Many2many(
        'ir.attachment',
        string='Attached Documents',
        help='Attach the pre-qualification or tender document and supporting files.',
    )

    # ── State ─────────────────────────────────────────────────────────────────

    state = fields.Selection([
        ('draft', 'Draft'),
        ('data_collection', 'Data Collection'),
        ('under_review', 'Under Review (Head of Contract)'),
        ('submitted_md', 'Submitted to MD'),
        ('md_approved', 'MD Approved'),
        ('md_rejected', 'MD Rejected'),
        ('revision', 'Revision Required'),
        ('submitted_client', 'Submitted to Client'),
    ], string='Status', default='draft', tracking=True)

    deadline_overdue = fields.Boolean(
        string='Submission Deadline Overdue',
        compute='_compute_deadline_overdue',
        store=True,
    )

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends('data_request_ids.state')
    def _compute_all_data_received(self):
        for rec in self:
            if not rec.data_request_ids:
                rec.all_data_received = False
            else:
                rec.all_data_received = all(
                    r.state == 'received' for r in rec.data_request_ids
                )

    @api.depends('client_submission_deadline')
    def _compute_deadline_overdue(self):
        today = fields.Date.today()
        for rec in self:
            rec.deadline_overdue = (
                bool(rec.client_submission_deadline)
                and rec.client_submission_deadline < today
                and rec.state not in ('submitted_client',)
            )

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_start_data_collection(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError('Only a draft record can move to data collection.')
        self.state = 'data_collection'

    def action_submit_for_review(self):
        self.ensure_one()
        if self.state != 'data_collection':
            raise UserError('Data collection must be active before submitting for review.')
        self.state = 'under_review'

    def action_submit_to_md(self):
        self.ensure_one()
        if self.state != 'under_review':
            raise UserError('The document must be reviewed by the Head of Contract first.')
        self.write({
            'state': 'submitted_md',
            'date_submitted_md': fields.Date.today(),
        })

    def action_md_approve(self):
        self.ensure_one()
        if self.state != 'submitted_md':
            raise UserError('The document must be submitted to MD before approval.')
        self.write({
            'state': 'md_approved',
            'md_decision': 'approved',
            'date_md_decision': fields.Date.today(),
        })

    def action_md_reject(self):
        self.ensure_one()
        self.write({
            'state': 'md_rejected',
            'md_decision': 'rejected',
            'date_md_decision': fields.Date.today(),
        })

    def action_request_revision(self):
        self.ensure_one()
        self.write({
            'state': 'revision',
            'md_decision': 'revision_required',
            'date_md_decision': fields.Date.today(),
        })

    def action_submit_to_client(self):
        self.ensure_one()
        if self.state != 'md_approved':
            raise UserError('MD approval is required before submitting to the client.')
        self.write({
            'state': 'submitted_client',
            'date_submitted_client': fields.Date.today(),
        })

    def action_reset_draft(self):
        self.ensure_one()
        if self.state in ('submitted_client',):
            raise UserError('A document already submitted to the client cannot be reset.')
        self.state = 'draft'