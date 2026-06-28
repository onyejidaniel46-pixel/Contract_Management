# -*- coding: utf-8 -*-
from odoo import models, fields


class ContractDashboard(models.TransientModel):
    _name = 'setraco.contract.dashboard'
    _description = 'Contract Dashboard (transient)'

    # Minimal transient model for dashboard display. No persistent fields required.
    name = fields.Char(string='Name')
    
    active_tender_count = fields.Integer(
        string='Active Tenders', compute='_compute_kpis')
    contract_count = fields.Integer(
        string='Contracts', compute='_compute_kpis')
    pending_md_count = fields.Integer(
        string='Pending MD', compute='_compute_kpis')
    overdue_claims_count = fields.Integer(
        string='Overdue Claims', compute='_compute_kpis')
    cost_alert_count = fields.Integer(
        string='Cost Alerts', compute='_compute_kpis')
    vop_open_count = fields.Integer(
        string='VOP Open', compute='_compute_kpis')

    def _compute_kpis(self):
        Tender = self.env['setraco.contract.tender']
        # Adjust model names/domains below to match your actual models & field names
        for rec in self:
            rec.active_tender_count = Tender.search_count(
                [('state', '=', 'open')]
            )
            rec.contract_count = self.env['setraco.contract.contract'].search_count(
                [('state', '=', 'active')]
            )
            rec.pending_md_count = self.env['setraco.contract.contract'].search_count(
                [('state', '=', 'pending_md')]
            )
            rec.overdue_claims_count = self.env['setraco.contract.claim'].search_count(
                [('payment_status', '=', 'overdue')]
            )
            rec.cost_alert_count = self.env['setraco.contract.cost.alert'].search_count(
                [('state', '=', 'open')]
            )
            rec.vop_open_count = self.env['setraco.contract.vop'].search_count(
                [('state', '=', 'pending_approval')]
            )
