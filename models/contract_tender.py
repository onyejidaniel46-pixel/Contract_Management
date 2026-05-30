# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date


class ContractTender(models.Model):
    _name = 'setraco.contract.tender'
    _description = 'Contract Tender'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_received desc, name'

    # ── Identity ──────────────────────────────────────────────────────────
    name = fields.Char(
        string='Tender Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    tender_title = fields.Char(
        string='Tender Title',
        required=True,
        tracking=True,
    )
    client_id = fields.Many2one(
        'res.partner',
        string='Client / Ministry',
        required=True,
        tracking=True,
    )
    project_type = fields.Selection([
        ('road_construction', 'Road Construction'),
        ('bridge', 'Bridge'),
        ('drainage', 'Drainage'),
        ('building', 'Building'),
        ('other', 'Other'),
    ], string='Project Type', required=True, default='road_construction', tracking=True)

    # ── Dates ─────────────────────────────────────────────────────────────
    date_received = fields.Date(
        string='Date Received',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    date_submission_deadline = fields.Date(
        string='Submission Deadline',
        tracking=True,
    )
    date_tender_opening = fields.Date(
        string='Tender Opening Date',
        tracking=True,
    )

    # ── Workflow Stage ─────────────────────────────────────────────────────
    state = fields.Selection([
        ('received',        '1. Received'),
        ('md_instruction',  '2. MD Instruction'),
        ('data_collection', '3. Data Collection'),
        ('estimation',      '4. Estimation'),
        ('md_review',       '5. MD Review'),
        ('submitted',       '6. Submitted to Client'),
        ('negotiation',     '7. Negotiation'),
        ('loi_received',    '8. LOI Received'),
        ('advance_payment', '9. Advance Payment'),
        ('contract_signed', '10. Contract Signed'),
        ('handover',        '11. Handover to Operations'),
        ('cancelled',       'Cancelled'),
    ], string='Stage', default='received', tracking=True, copy=False)

    # ── MD Instruction ────────────────────────────────────────────────────
    md_instruction_date = fields.Date(string='MD Instruction Date', tracking=True)
    md_instruction_notes = fields.Text(string='MD Instruction Notes')
    md_user_id = fields.Many2one(
        'res.users', string='Managing Director',
        domain="[('groups_id.name','=','Setraco MD')]",
    )

    # ── Data Collection Flags ─────────────────────────────────────────────
    cost_control_data = fields.Boolean(string='Cost Control Data Received', tracking=True)
    procurement_data   = fields.Boolean(string='Procurement / BOQ Data Received', tracking=True)
    plant_data         = fields.Boolean(string='Plant Equipment Rates Received', tracking=True)
    personnel_data     = fields.Boolean(string='Personnel Labour Rates Received', tracking=True)
    operational_data   = fields.Boolean(string='Operational Costs Received', tracking=True)
    data_collection_complete = fields.Boolean(
        string='All Data Collected',
        compute='_compute_data_collection_complete',
        store=True,
    )

    @api.depends(
        'cost_control_data', 'procurement_data',
        'plant_data', 'personnel_data', 'operational_data',
    )
    def _compute_data_collection_complete(self):
        for rec in self:
            rec.data_collection_complete = all([
                rec.cost_control_data, rec.procurement_data,
                rec.plant_data, rec.personnel_data, rec.operational_data,
            ])

    # ── Estimation Link ───────────────────────────────────────────────────
    estimation_id = fields.Many2one(
        'setraco.contract.estimation',
        string='Estimation',
        copy=False,
    )
    estimation_count = fields.Integer(
        compute='_compute_estimation_count',
        string='Estimations',
    )

    @api.depends('estimation_id')
    def _compute_estimation_count(self):
        for rec in self:
            rec.estimation_count = 1 if rec.estimation_id else 0

    # ── Agreement Link ────────────────────────────────────────────────────
    agreement_id = fields.Many2one(
        'setraco.contract.agreement',
        string='Contract Agreement',
        copy=False,
    )

    # ── Negotiation / LOI ─────────────────────────────────────────────────
    loi_date = fields.Date(string='LOI Date Received', tracking=True)
    loi_document = fields.Binary(string='LOI Document', attachment=True)
    loi_filename = fields.Char(string='LOI Filename')

    # ── Advance Payment ───────────────────────────────────────────────────
    advance_payment_requested = fields.Boolean(string='Advance Payment Requested', tracking=True)
    advance_payment_amount = fields.Monetary(
        string='Advance Payment Amount',
        currency_field='currency_id',
        tracking=True,
    )
    advance_payment_received = fields.Boolean(string='Advance Payment Received', tracking=True)
    advance_payment_date = fields.Date(string='Advance Payment Date', tracking=True)
    performance_guarantee = fields.Boolean(string='Performance Guarantee Acquired', tracking=True)
    performance_guarantee_source = fields.Selection([
        ('accounts', 'Accounts Department'),
        ('bank', 'Bank'),
    ], string='Guarantee Source', tracking=True)

    # ── Financial ─────────────────────────────────────────────────────────
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    contract_value = fields.Monetary(
        string='Contract Value',
        currency_field='currency_id',
        tracking=True,
    )

    # ── Responsible ───────────────────────────────────────────────────────
    head_of_contract_id = fields.Many2one(
        'res.users',
        string='Head of Contract',
        default=lambda self: self.env.user,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    # ── Notes ─────────────────────────────────────────────────────────────
    description = fields.Html(string='Description / Notes')
    cancellation_reason = fields.Text(string='Cancellation Reason')

    # ─────────────────────────────────────────────────────────────────────
    # ORM Overrides
    # ─────────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'setraco.contract.tender'
                ) or _('New')
        return super().create(vals_list)

    # ─────────────────────────────────────────────────────────────────────
    # Workflow Actions
    # ─────────────────────────────────────────────────────────────────────
    def action_send_to_md(self):
        """Stage 2 – Record MD instruction to proceed."""
        self.ensure_one()
        if self.state != 'received':
            raise UserError(_('Tender must be in Received stage.'))
        self.write({'state': 'md_instruction', 'md_instruction_date': fields.Date.today()})
        self.message_post(body=_('MD instructed Contract Department to proceed.'))

    def action_start_data_collection(self):
        """Stage 3 – Begin collecting data from departments."""
        self.ensure_one()
        if self.state != 'md_instruction':
            raise UserError(_('Tender must be in MD Instruction stage.'))
        self.write({'state': 'data_collection'})

    def action_create_estimation(self):
        """Stage 4 – Create linked estimation record."""
        self.ensure_one()
        if not self.data_collection_complete:
            raise UserError(_('All departmental data must be received before creating estimation.'))
        if self.estimation_id:
            raise UserError(_('An estimation already exists for this tender.'))
        estimation = self.env['setraco.contract.estimation'].create({
            'tender_id': self.id,
            'client_id': self.client_id.id,
            'currency_id': self.currency_id.id,
        })
        self.write({'estimation_id': estimation.id, 'state': 'estimation'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'setraco.contract.estimation',
            'res_id': estimation.id,
            'view_mode': 'form',
        }

    def action_submit_for_md_review(self):
        """Stage 5 – Submit prepared tender doc to MD for approval."""
        self.ensure_one()
        if not self.estimation_id:
            raise UserError(_('Estimation must be completed before MD review.'))
        self.write({'state': 'md_review'})
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.md_user_id.id or self.env.user.id,
            summary=_('Tender approval required: %s') % self.name,
            note=_('Please review and approve the tender document for %s.') % self.tender_title,
        )

    def action_md_approve_submit(self):
        """Open MD Approval Wizard."""
        self.ensure_one()
        if self.state != 'md_review':
            raise UserError(_('Tender must be in MD Review stage.'))
        return {
            'name': _('MD Approval Decision'),
            'type': 'ir.actions.act_window',
            'res_model': 'setraco.contract.md.approval.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_tender_id': self.id,
            }
        }

    def action_start_negotiation(self):
        """Stage 7 – Tender opened; negotiations begin."""
        self.ensure_one()
        self.write({'state': 'negotiation'})

    def action_record_loi(self):
        """Stage 8 – LOI received from client."""
        self.ensure_one()
        self.write({'state': 'loi_received', 'loi_date': fields.Date.today()})
        self.message_post(body=_('Letter of Intent received from client.'))

    def action_request_advance_payment(self):
        """Stage 9 – Request advance payment after LOI acceptance."""
        self.ensure_one()
        if not self.loi_date:
            raise UserError(_('LOI must be recorded before requesting advance payment.'))
        self.write({'state': 'advance_payment', 'advance_payment_requested': True})

    def action_confirm_advance_payment(self):
        """Open Advance Payment Wizard."""
        self.ensure_one()
        if self.state != 'advance_payment':
            raise UserError(_('Tender must be in Advance Payment stage.'))
        return {
            'name': _('Confirm Advance Payment Received'),
            'type': 'ir.actions.act_window',
            'res_model': 'setraco.contract.advance.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_tender_id': self.id,
                'default_amount': self.advance_payment_amount or 0.0,
            }
        }

    def action_sign_contract(self):
        """Stage 10 – Contract agreement finalised."""
        self.ensure_one()
        if not self.advance_payment_received:
            raise UserError(_('Advance payment must be confirmed before signing contract.'))
        if not self.performance_guarantee:
            raise UserError(_('Performance guarantee must be acquired before signing.'))
        agreement = self.env['setraco.contract.agreement'].create({
            'tender_id': self.id,
            'client_id': self.client_id.id,
            'contract_value': self.contract_value,
            'currency_id': self.currency_id.id,
            'date_signed': fields.Date.today(),
        })
        self.write({'state': 'contract_signed', 'agreement_id': agreement.id})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'setraco.contract.agreement',
            'res_id': agreement.id,
            'view_mode': 'form',
        }

    def action_handover_operations(self):
        """Stage 11 – Hand completed contract docs to Operations."""
        self.ensure_one()
        if self.state != 'contract_signed':
            raise UserError(_('Contract must be signed before handover.'))
        self.write({'state': 'handover'})
        self.message_post(
            body=_('Contract documents handed over to Operations team. '
                'Project Department assigned for execution.')
        )

    def action_cancel(self):
        self.ensure_one()
        self.write({'state': 'cancelled'})

    def action_reset_to_received(self):
        self.ensure_one()
        self.write({'state': 'received'})

    # ─────────────────────────────────────────────────────────────────────
    # Smart Button Actions
    # ─────────────────────────────────────────────────────────────────────
    def action_view_estimation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'setraco.contract.estimation',
            'res_id': self.estimation_id.id,
            'view_mode': 'form',
        }

    def action_view_agreement(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'setraco.contract.agreement',
            'res_id': self.agreement_id.id,
            'view_mode': 'form',
        }