# coding=utf-8
import logging
import base64
import csv
import StringIO
from datetime import datetime

from openerp.osv import osv, fields
# noinspection PyProtectedMember
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

_logger = logging.getLogger(__name__)

from openerp.addons.account_bank_statement_import import account_bank_statement_import as ibs

ibs.add_file_type(('op_csv', 'Osuuspankki'))

SIGNATURE = [
    'Kirjauspäivä;Arvopäivä;Määrä EUROA;Laji;Selitys;Saaja/Maksaja;Saajan tilinumero ja pankin BIC;Viite;Viesti;'
    'Arkistointitunnus'
]

COL_DATE = 1
COL_AMOUNT = 2
COL_PAYEE = 5
COL_PAYEE_ACCOUNT = 6
COL_REFNUM = 7
COL_MEMO = 8
COL_ID = 9

DATE_FORMAT = '%d.%m.%Y'


class Transaction():
    # A unique transaction reference
    """
    A single transaction in a bank statement
    :param row: The row of a CSV file
    """
    id = None

    # Payment reference
    ref = None

    # Value date
    date = None

    # Description
    name = ''

    # The other party of the payment
    payee = ''

    # Negative or positive amount of money transferred
    amount = 0.0

    # Bank account number
    bank_account = None

    def __init__(self, row):
        self.id = row[COL_ID]  # Not in use
        self.date = datetime.strptime(row[COL_DATE], DATE_FORMAT)
        self.name = row[COL_PAYEE] + ': ' + row[COL_MEMO]
        self.payee = row[COL_PAYEE]
        self.amount = float(row[COL_AMOUNT].replace(',', '.'))

        # The last part is just the bank identifier
        self.bank_account = row[COL_PAYEE_ACCOUNT][:row[COL_PAYEE_ACCOUNT].rfind(' ')]


class AccountBankStatementImport(osv.TransientModel):
    _inherit = 'account.bank.statement.import'

    _columns = {
        'balance_start': fields.float(
            'Starting Balance',
            digits_compute=dp.get_precision('Account')
        )
    }

    def parse_file(self, cr, uid, ids, context=None):
        if not context:
            context = {}

        data = self.browse(cr, uid, ids[0], context=context)
        context['statement_balance_start'] = data.balance_start

        return super(AccountBankStatementImport, self).parse_file(cr, uid, ids, context)

    def process_op_csv(self, cr, uid, data_file, journal_id=False, context=None):
        """ Import a file in the Osuuspankki .CSV format"""
        try:
            csv_text = base64.decodestring(data_file).decode('iso-8859-1').encode('utf-8')
            stream = StringIO.StringIO(csv_text)
            reader = csv.reader(stream, delimiter=';')
        except:
            raise osv.except_osv(_('Import Error!'), _('Please make sure the file format is CSV.'))

        line_ids = []
        total_amt = 0.00
        min_date = False
        max_date = False

        header = ';'.join(next(reader, None))
        if header not in SIGNATURE:
            raise osv.except_osv(_('Import Error!'), _('CSV column headers invalid. Possible values: ')
                                 + SIGNATURE)

        try:
            for row in reader:
                if not row:
                    continue

                transaction = Transaction(row)
                bank_account_id, partner_id = self._detect_partner(cr, uid, transaction.bank_account,
                                                                   identifying_field='acc_number', context=context)

                if not bank_account_id or not partner_id:
                    bank_account_id, partner_id = self._detect_partner(cr, uid, transaction.payee,
                                                                       identifying_field='owner_name', context=context)

                if not min_date or transaction.date < min_date:
                    min_date = transaction.date
                if not max_date or transaction.date > max_date:
                    max_date = transaction.date

                vals_line = {
                    'date': transaction.date,
                    'name': transaction.name,
                    'ref': transaction.ref,
                    'amount': transaction.amount,
                    'partner_id': partner_id,
                    'bank_account_id': bank_account_id
                }

                total_amt += float(transaction.amount)
                line_ids.append((0, 0, vals_line))
        except Exception, e:
            raise osv.except_osv(_('Error!'), _(
                u"Following problem has been occurred while importing your file, "
                u"Please make sure the file is valid.\n\n {}").format(e.message))

        period_obj = self.pool.get('account.period')
        if max_date:
            period_ids = period_obj.find(cr, uid, max_date, context=context)
        else:
            period_ids = period_obj.find(cr, uid, min_date, context=context)

        balance_start = context.get('statement_balance_start', 0.0)
        vals_bank_statement = {
            'balance_start': balance_start,
            'balance_end_real': balance_start + total_amt,
            'period_id': period_ids and period_ids[0] or False,
            'journal_id': journal_id
        }

        vals_bank_statement.update({'line_ids': line_ids})

        return [vals_bank_statement]
