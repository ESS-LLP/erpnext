from __future__ import unicode_literals

data = {
	'desktop_icons': [
		'Patient',
		'Patient Appointment',
		'Patient Encounter',
		'Lab Test',
		'Healthcare',
		'Vital Signs',
		'Clinical Procedure',
		'Inpatient Record',
		'Accounts',
		'Buying',
		'Stock',
		'HR',
		'ToDo'
	],
	'default_portal_role': 'Patient',
	'restricted_roles': [
		'Healthcare Administrator',
		'LabTest Approver',
		'Laboratory User',
		'Nursing User',
		'Physician',
		'Patient'
	],
	'custom_fields': {
		'Sales Invoice': [
			{
				'fieldname': 'patient', 'label': 'Patient', 'fieldtype': 'Link', 'options': 'Patient',
				'insert_after': 'naming_series'
			},
			{
				'fieldname': 'patient_name', 'label': 'Patient Name', 'fieldtype': 'Data', 'fetch_from': 'patient.patient_name',
				'insert_after': 'patient', 'read_only': True
			},
			{
				'fieldname': 'inpatient_record', 'label': 'Inpatient Record', 'fieldtype': 'Link', 'fetch_from': 'patient.inpatient_record',
				'insert_after': 'patient_name', 'read_only': True, 'fetch_if_empty': True, 'options': 'Inpatient Record'
			},
			{
				'fieldname': 'ref_practitioner', 'label': 'Referring Practitioner', 'fieldtype': 'Link', 'options': 'Healthcare Practitioner',
				'insert_after': 'customer'
			},
			{
				'fieldname': 'total_insurance_claim_amount', 'label': 'Total Insurance Claim Amount', 'fieldtype': 'Currency',
				'insert_after': 'total', 'read_only':True
			},
			{
				'fieldname': 'patient_payable_amount', 'label': 'Patient Payable Amount', 'fieldtype': 'Currency',
				'insert_after': 'total_insurance_claim_amount', 'read_only':True,
				'depends_on':'eval:doc.docstatus < 1 && doc.total_insurance_claim_amount && doc.total_insurance_claim_amount > 0'
			},
			{
				'fieldname': 'practitioner_revenue_sharing', 'label': 'Practitioner Revenue Sharing Distribution', 'fieldtype': 'Section Break',
				'insert_after': 'discount_amount'
			},
			{
				'fieldname': 'practitioner_revenue_distributions', 'label': 'Practitioner Revenue Distributions', 'fieldtype': 'Table', 'options': 'Practitioner Revenue Distribution',
				'insert_after': 'practitioner_revenue_sharing'
			},
			{
				'fieldname': 'total_doctors_charges', 'label': 'Total Doctors Charges', 'fieldtype': 'Currency',
				'insert_after': 'practitioner_revenue_distributions', 'read_only':True
			},
			{
				'fieldname': 'insurance', 'label': 'Insurance Assignment ', 'fieldtype': 'Link', 'options': 'Insurance Assignment',
				'insert_after': 'ref_practitioner'
			},
			{
				'fieldname': 'insurance_company', 'label': 'Insurance Company', 'fieldtype': 'Data',
				'insert_after': 'insurance', 'read_only':True
			},
			{
				'fieldname': 'healthcare_insurance_pricelist', 'label': 'Healthcare Insurance PriceList ', 'fieldtype': 'Link', 'options': 'Price List',
				'insert_after': 'selling_price_list', 'read_only':True
			},
		],
		'Sales Invoice Item': [
			{
				'fieldname': 'reference_dt', 'label': 'Reference DocType', 'fieldtype': 'Link', 'options': 'DocType',
				'insert_after': 'edit_references'
			},
			{
				'fieldname': 'reference_dn', 'label': 'Reference Name', 'fieldtype': 'Dynamic Link', 'options': 'reference_dt',
				'insert_after': 'reference_dt'
			},
			{
				'fieldname': 'insurance_claim_coverage', 'label': 'Insurance Claim Coverage', 'fieldtype': 'Percent',
				'insert_after': 'amount', 'read_only':True
			},
			{
				'fieldname': 'insurance_claim_amount', 'label': 'Insurance Claim Amount', 'fieldtype': 'Currency',
				'insert_after': 'insurance_claim_coverage', 'read_only':True
			},
			{
				'fieldname': 'insurance_approval_number', 'label': 'Insurance Approval Number', 'fieldtype': 'Data',
				'insert_after': 'insurance_claim_amount', 'read_only':True
			}
		],
		'Delivery Note': [
			{
				'fieldname': 'patient', 'label': 'Patient', 'fieldtype': 'Link', 'options': 'Patient',
				'insert_after': 'naming_series'
			},
			{
				'fieldname': 'patient_name', 'label': 'Patient Name', 'fieldtype': 'Data', 'fetch_from': 'patient.patient_name',
				'insert_after': 'patient', 'read_only': True
			},
			{
				'fieldname': 'inpatient_record', 'label': 'Inpatient Record', 'fieldtype': 'Link', 'fetch_from': 'patient.inpatient_record',
				'insert_after': 'patient_name', 'read_only': True, 'fetch_if_empty': True, 'options': 'Inpatient Record'
			},
			{
				'fieldname': 'source_service_unit', 'label': 'Source Healthcare Service Unit', 'fieldtype': 'Link',
				'insert_after': 'sec_warehouse', 'options': 'Healthcare Service Unit'
			},
			{
				'fieldname': 'set_cost_center', 'label': 'Cost Center', 'fieldtype': 'Link', 'fetch_from': 'source_service_unit.cost_center',
				'insert_after': 'set_warehouse', 'fetch_if_empty': True, 'options': 'Cost Center', 'depends_on': 'source_service_unit'
			},
			{
				'fieldname': 'insurance', 'label': 'Insurance', 'fieldtype': 'Link', 'insert_after': 'customer_name',
				'options': 'Insurance Assignment'
			},
			{
				'fieldname': 'insurance_company_name', 'label': 'Insurance Company Name', 'fieldtype': 'Data',
				'fetch_from': 'insurance.insurance_company_name', 'read_only': True, 'insert_after': 'insurance', 'fetch_if_empty': True,
				'depends_on': 'insurance'
			},
			{
				'fieldname': 'insurance_approval_number', 'label': 'Insurance Approval Number', 'fieldtype': 'Data',
				'insert_after': 'insurance_company_name', 'depends_on': 'insurance'
			},
			{
				'fieldname': 'insurance_remarks', 'label': 'Insurance Remarks', 'fieldtype': 'Small Text',
				'insert_after': 'return_against', 'depends_on': 'insurance'
			}

		],
		'Delivery Note Item': [
			{
				'fieldname': 'reference_dt', 'label': 'Reference DocType', 'fieldtype': 'Link', 'options': 'DocType',
				'insert_after': 'page_break'
			},
			{
				'fieldname': 'reference_dn', 'label': 'Reference Name', 'fieldtype': 'Dynamic Link', 'options': 'reference_dt',
				'insert_after': 'reference_dt'
			}
		],
		'Payment Entry': [
			{
				'fieldname': 'patient', 'label': 'Patient', 'fieldtype': 'Link', 'options': 'Patient',
				'insert_after': 'party_section'
			},
			{
				'fieldname': 'patient_name', 'label': 'Patient Name', 'fieldtype': 'Data', 'fetch_from': 'patient.patient_name',
				'insert_after': 'patient', 'read_only': True
			},
			{
				'fieldname': 'inpatient_record', 'label': 'Inpatient Record', 'fieldtype': 'Link', 'fetch_from': 'patient.inpatient_record',
				'insert_after': 'patient_name', 'read_only': True, 'fetch_if_empty': True, 'options': 'Inpatient Record'
			}
		],
	},
	'on_setup': 'erpnext.healthcare.setup.setup_healthcare'
}
