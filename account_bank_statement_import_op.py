# coding=utf-8
import logging
import base64
import csv
import StringIO
from datetime import datetime

from openerp import models, fields, api

# noinspection PyProtectedMember
from openerp.tools.translate import _
from openerp.exceptions import ValidationError

# noinspection PyUnresolvedReferences
import openerp.addons.decimal_precision as dp

_logger = logging.getLogger(__name__)

SIGNATURE = [
    'Kirjauspäivä;Arvopäivä;Määrä EUROA;Laji;Selitys;Saaja/Maksaja;'
    'Saajan tilinumero ja pankin BIC;Viite;Viesti;Arkistointitunnus'
]

COL_DATE = 1
COL_AMOUNT = 2
COL_PARTNER = 5
COL_PAYEE_ACCOUNT = 6
COL_REFNUM = 7
COL_MEMO = 8
COL_ID = 9

DATE_FORMAT = '%d.%m.%Y'


class Transaction(object):
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
    partner_name = ''

    # Negative or positive amount of money transferred
    amount = 0.0

    # Bank account number
    bank_account = None

    def __init__(self, row):
        self.id = row[COL_ID]
        self.date = datetime.strptime(row[COL_DATE], DATE_FORMAT)
        self.name = row[COL_PARTNER] + ': ' + row[COL_MEMO]
        self.partner_name = row[COL_PARTNER]
        self.amount = float(row[COL_AMOUNT].replace(',', '.'))
        self.ref = row[COL_REFNUM]

        # The last part is just the bank identifier
        identifier = row[COL_PAYEE_ACCOUNT].rfind(' ')
        self.bank_account = row[COL_PAYEE_ACCOUNT][:identifier]


class AccountBankStatementImport(models.TransientModel):
    _inherit = 'account.bank.statement.import'

    balance_start = fields.Float(
        'Starting Balance',
        digits_compute=dp.get_precision('Account')
    )

    bank_statement_date = fields.Date(
        'Bank Statement Date',
        help="You can choose to manually set the bank statement date here. "
             "Otherwise the bank statement date will be read from the latest "
             "bank statement line.",
    )

    @api.model
    def _check_osuuspankki(self):
        # noinspection PyBroadException
        try:
            osuuspankki = self.process_op_csv()
        except:
            return False, False, False
        return osuuspankki

    @api.model
    def _parse_file(self, data_file):
        result = self._check_osuuspankki()
        if not result[2]:
            # noinspection PyProtectedMember,PyUnresolvedReferences
            return super(AccountBankStatementImport, self) \
                ._parse_file(data_file)

        return result

    def process_op_csv(self):
        """ Import a file in the Osuuspankki .CSV format"""
        try:
            # noinspection PyUnresolvedReferences
            csv_text = base64\
                .decodestring(self.data_file)\
                .decode('iso-8859-1') \
                .encode('utf-8')
            stream = StringIO.StringIO(csv_text)
            reader = csv.reader(stream, delimiter=';')
        except:
            raise ValidationError(
                _('Please make sure the file format is CSV.')
            )

        transactions = []
        total_amt = 0.00
        min_date = max_date = False
        index = 0

        header = ';'.join(next(reader, None))
        if header not in SIGNATURE:
            raise ValidationError(
                _('CSV column headers invalid. Possible values: ') + SIGNATURE
            )

        try:
            for row in reader:
                if not row:
                    continue

                transaction = Transaction(row)
                # noinspection PyUnresolvedReferences
                bank_account_id = self._find_bank_account_id(
                    transaction.bank_account
                )

                if not min_date or transaction.date < min_date:
                    min_date = transaction.date
                if not max_date or transaction.date < max_date:
                    max_date = transaction.date

                # Transaction ID is not unique, transaction ID with date is
                # not unique. Let's hope that transaction ID, date and index
                # is.
                import_id = transaction.id + str(transaction.date) + str(index)
                vals_line = {
                    'unique_import_id': import_id,
                    'date': transaction.date,
                    'name': transaction.name,
                    'ref': transaction.ref,
                    'amount': transaction.amount,
                    'partner_name': transaction.partner_name,
                    'bank_account_id': bank_account_id
                }

                total_amt += float(transaction.amount)
                transactions.append(vals_line)
                index += 1
        except Exception, e:
            raise ValidationError(
                _(u"Following problem has been occurred while importing "
                  u"your file. Please make sure the file is valid.\n\n {}")
                .format(e.message))

        # noinspection PyTypeChecker
        vals_bank_statement = {
            'balance_start': self.balance_start,
            'balance_end_real': self.balance_start + total_amt,
            'date': self.bank_statement_date
            if self.bank_statement_date else max_date,
            'transactions': transactions
        }

        return 'EUR', None, [vals_bank_statement]
