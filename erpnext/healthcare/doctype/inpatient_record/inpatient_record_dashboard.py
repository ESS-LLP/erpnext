from __future__ import unicode_literals
from frappe import _

def get_data():
	return {
		'fieldname': 'inpatient_record',
		'transactions': [
			{
				'label': _('Appointments and Encounters'),
				'items': ['Patient Appointment', 'Patient Encounter']
			},
			{
				'label': _('Diagnostics'),
 				'items': ['Lab Test', 'Sample Collection', 'Vital Signs', 'Radiology Examination']
			},
			{
				'label': _('Procedures'),
 				'items': ['Clinical Procedure', 'Healthcare Nursing Task']
			},
			{
				'label': _('Rehabilitation and Physiotherapy'),
 				'items': ['Therapy Plan', 'Therapy Session', 'Patient Assessment']
			}
		]
	}
