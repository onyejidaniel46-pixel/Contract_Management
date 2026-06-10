# -*- coding: utf-8 -*-
from odoo import models, fields


class ContractDashboard(models.TransientModel):
    _name = 'setraco.contract.dashboard'
    _description = 'Contract Dashboard (transient)'

    # Minimal transient model for dashboard display. No persistent fields required.
    name = fields.Char(string='Name')
