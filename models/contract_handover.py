from odoo import models, fields, api
from odoo.exceptions import UserError


class ContractHandover(models.Model):
    _name = 'setraco.contract.handover'
    _description = 'Contract Handover to Operations & Project Department'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'handover_date desc'

    name = fields.Char(
        string='Handover Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('setraco.contract.handover'),
    )
    contract_id = fields.Many2one(
        'setraco.contract.agreement',
        string='Contract',
        required=True,
        tracking=True,
        ondelete='restrict',
    )
    tender_id = fields.Many2one(
        related='contract_id.tender_id',
        string='Tender',
        store=True,
    )
    client_id = fields.Many2one(
        related='contract_id.client_id',
        string='Client',
        store=True,
    )
    contract_value = fields.Monetary(
        related='contract_id.contract_value',
        string='Contract Value',
        currency_field='currency_id',
        store=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )

    # ── Dates ─────────────────────────────────────────────────────────────────

    handover_date = fields.Date(
        string='Handover Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    project_start_date = fields.Date(
        string='Expected Project Start Date',
        tracking=True,
    )
    project_end_date = fields.Date(
        string='Expected Completion Date',
        tracking=True,
    )

    # ── Responsible Parties ───────────────────────────────────────────────────

    handed_over_by = fields.Many2one(
        'res.users',
        string='Handed Over By (Contract Dept)',
        default=lambda self: self.env.user,
        tracking=True,
    )
    received_by = fields.Many2one(
        'res.users',
        string='Received By (Operations)',
        tracking=True,
    )
    project_manager_id = fields.Many2one(
        'res.users',
        string='Assigned Project Manager',
        tracking=True,
    )
    project_id = fields.Many2one(
        'project.project',
        string='Linked Odoo Project',
        tracking=True,
        help='Link to the Odoo Project created for execution tracking.',
    )

    # ── Documents Checklist ───────────────────────────────────────────────────

    checklist_ids = fields.One2many(
        'setraco.contract.handover.checklist',
        'handover_id',
        string='Document Checklist',
    )
    all_documents_submitted = fields.Boolean(
        string='All Documents Submitted',
        compute='_compute_all_docs_submitted',
        store=True,
    )

    # ── Narrative ─────────────────────────────────────────────────────────────

    contract_summary = fields.Html(
        string='Contract Summary / Key Terms',
        help='Summary of contract scope, obligations, and key clauses for the operations team.',
    )
    special_instructions = fields.Text(
        string='Special Instructions to Project Team',
    )
    notes = fields.Html(string='Additional Notes')
    document_ids = fields.Many2many(
        'ir.attachment',
        string='Handover Documents',
        help='Attach signed contract, programme of works, BOQ, and any client-required docs.',
    )

    # ── State ─────────────────────────────────────────────────────────────────

    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_ops', 'Pending Operations Acceptance'),
        ('accepted', 'Accepted by Operations'),
        ('project_assigned', 'Project Assigned'),
        ('complete', 'Handover Complete'),
    ], string='Status', default='draft', tracking=True)

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends('checklist_ids.is_submitted')
    def _compute_all_docs_submitted(self):
        for rec in self:
            if not rec.checklist_ids:
                rec.all_documents_submitted = False
            else:
                rec.all_documents_submitted = all(
                    line.is_submitted for line in rec.checklist_ids
                )

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_send_to_operations(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError('Only a draft handover can be sent to Operations.')
        if not self.received_by:
            raise UserError('Please assign an Operations receiver before sending.')
        self.state = 'pending_ops'

    def action_accept_handover(self):
        self.ensure_one()
        if self.state != 'pending_ops':
            raise UserError('Only a pending handover can be accepted.')
        self.state = 'accepted'

    def action_assign_project(self):
        self.ensure_one()
        if self.state not in ('accepted', 'pending_ops'):
            raise UserError('The handover must be accepted before assigning a project.')
        if not self.project_manager_id:
            raise UserError('Please assign a Project Manager before proceeding.')
        self.state = 'project_assigned'

    def action_complete(self):
        self.ensure_one()
        if self.state != 'project_assigned':
            raise UserError('A project must be assigned before completing the handover.')
        if not self.all_documents_submitted:
            raise UserError('All checklist documents must be submitted before completing the handover.')
        self.state = 'complete'

    def action_reset_draft(self):
        self.ensure_one()
        if self.state == 'complete':
            raise UserError('A completed handover cannot be reset.')
        self.state = 'draft'


class ContractHandoverChecklist(models.Model):
    _name = 'setraco.contract.handover.checklist'
    _description = 'Handover Document Checklist Line'
    _order = 'sequence, id'

    handover_id = fields.Many2one(
        'setraco.contract.handover',
        string='Handover',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(string='Seq.', default=10)
    document_name = fields.Char(
        string='Document',
        required=True,
    )
    document_type = fields.Selection([
        ('contract_agreement', 'Signed Contract Agreement'),
        ('boq', 'Bill of Quantities (BOQ)'),
        ('programme_of_works', 'Programme of Works'),
        ('loi', 'Letter of Intent'),
        ('performance_guarantee', 'Performance Guarantee'),
        ('insurance', 'Insurance Certificate'),
        ('drawings', 'Engineering Drawings'),
        ('advance_payment', 'Advance Payment Evidence'),
        ('other', 'Other'),
    ], string='Document Type', default='other')
    is_required = fields.Boolean(string='Required', default=True)
    is_submitted = fields.Boolean(string='Submitted', default=False)
    submitted_date = fields.Date(string='Date Submitted')
    remarks = fields.Char(string='Remarks')

    @api.onchange('is_submitted')
    def _onchange_submitted(self):
        if self.is_submitted and not self.submitted_date:
            self.submitted_date = fields.Date.today()
        elif not self.is_submitted:
            self.submitted_date = False