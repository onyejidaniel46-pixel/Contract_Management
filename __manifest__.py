# -*- coding: utf-8 -*-
{
    'name': 'Setraco Contract Management',
    'version': '17.0.1.0.0',
    'category': 'Construction/Contract',
    'summary': 'End-to-end contract lifecycle management for Setraco Nigeria Limited',
    'description': """
        Setraco Contract Management Module
        ====================================
        Covers the full contract lifecycle:
        - Tender notification and data collection
        - Estimation (BOQ, labor, equipment, operational costs)
        - MD approval workflow
        - Letter of Intent (LOI) and advance payment
        - Contract agreement and handover to operations
        - Claims certificates and payment tracking
        - VOP (Variation of Price) management
        - RETC (Revised Estimated Total Cost) tracking
        - Cost alert system (dry cost / selling cost)
        - Daily, monthly, and ad-hoc reporting
        - Document Management System (DMS) integration
    """,
    'depends': ['base', 'mail', 'project'],
    'data': [
        # Security
        'security/setraco_contract_security.xml',
        'security/ir.model.access.csv',

        # Data / Sequences
        'data/setraco_contract_sequence.xml',
        'data/setraco_contract_data.xml',

        # Views
        'views/contract_tender_views.xml',
        'views/contract_estimation_views.xml',
        'views/contract_agreement_views.xml',
        'views/contract_claim_views.xml',
        'views/contract_vop_views.xml',
        'views/contract_cost_alert_views.xml',
        'views/contract_report_views.xml',
        'views/contract_prequalification_views.xml',
        'views/contract_dashboard_views.xml',
        'views/contract_boq_views.xml',
        'views/contract_loi_views.xml',
        'views/contract_advance_payment_views.xml',
        'views/contract_retc_views.xml',
        'views/contract_menu_views.xml',

        # Wizards
        'wizard/contract_md_approval_wizard_views.xml',
        'wizard/contract_advance_payment_wizard_views.xml',

        # Reports
        'reports/contract_tender_report.xml',
        'reports/contract_claim_certificate.xml',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}