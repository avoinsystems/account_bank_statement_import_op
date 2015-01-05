{
    'name': 'Import Osuuspankki Bank Statement',
    'version': '1.0',
    'author': 'Avoin.Systems',
    'depends': ['account_bank_statement_import'],
    'category': 'Accounting',
    'demo': [],
    'description': """
Module to import bank statements of the Finnish bank Osuuspankki.
=================================================================

This module allows you to import the machine readable CSV Files in Odoo: they are parsed
and stored in human readable format in Accounting \ Bank and Cash \ Bank Statements.

    """,
    'data': [
        'view/import_statement.xml'
    ],
    'demo': [],
    'auto_install': False,
    'installable': True,
}
