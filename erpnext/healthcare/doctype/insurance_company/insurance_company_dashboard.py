from __future__ import unicode_literals
from frappe import _

def get_data():
	return {
		'fieldname': 'insurance_company',
		'transactions': [
			{
				'label': _('Insurance Contract'),
				'items': ['Insurance Contract']
			},
		]
	}
