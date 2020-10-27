# -*- coding: utf-8 -*-
# Copyright (c) 2018, earthians and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import math
import frappe
from frappe import _
from frappe.utils import time_diff_in_hours, rounded, getdate, nowdate
from erpnext.healthcare.doctype.healthcare_settings.healthcare_settings import get_income_account
from erpnext.healthcare.doctype.fee_validity.fee_validity import create_fee_validity
from erpnext.healthcare.doctype.lab_test.lab_test import create_multiple

@frappe.whitelist()
def get_healthcare_services_to_invoice(patient, company):
	patient = frappe.get_doc('Patient', patient)
	items_to_invoice = []
	if patient:
		validate_customer_created(patient)
		# Customer validated, build a list of billable services
		items_to_invoice += get_appointments_to_invoice(patient, company)
		items_to_invoice += get_encounters_to_invoice(patient, company)
		items_to_invoice += get_lab_tests_to_invoice(patient, company)
		items_to_invoice += get_clinical_procedures_to_invoice(patient, company)
		items_to_invoice += get_inpatient_services_to_invoice(patient, company)
		items_to_invoice += get_therapy_sessions_to_invoice(patient, company)
		items_to_invoice += get_radiology_examinations_to_invoice(patient, company)
		items_to_invoice += get_healthcare_service_orders_to_invoice(patient, company)

		return items_to_invoice


def validate_customer_created(patient):
	if not frappe.db.get_value('Patient', patient.name, 'customer'):
		msg = _("Please set a Customer linked to the Patient")
		msg +=  " <b><a href='#Form/Patient/{0}'>{0}</a></b>".format(patient.name)
		frappe.throw(msg, title=_('Customer Not Found'))

def get_appointments_to_invoice(patient, company):
	appointments_to_invoice = []
	patient_appointments = frappe.get_list(
			'Patient Appointment',
			fields = '*',
			filters = {'patient': patient.name, 'company': company, 'invoiced': 0, 'status': ['not in', 'Cancelled']},
			order_by = 'appointment_date'
		)

	for appointment in patient_appointments:
		# Procedure Appointments
		if appointment.procedure_template:
			if frappe.db.get_value('Clinical Procedure Template', appointment.procedure_template, 'is_billable'):
				appointments_to_invoice.append({
					'reference_type': 'Patient Appointment',
					'reference_name': appointment.name,
					'service': appointment.procedure_template
				})
		# Consultation Appointments, should check fee validity
		else:
			if frappe.db.get_single_value('Healthcare Settings', 'enable_free_follow_ups') and \
				frappe.db.exists('Fee Validity Reference', {'appointment': appointment.name}):
					continue # Skip invoicing, fee validty present
			practitioner_charge = 0
			income_account = None
			service_item = None
			if appointment.practitioner:
				service_item, practitioner_charge = get_service_item_and_practitioner_charge(appointment)
				income_account = get_income_account(appointment.practitioner, appointment.company)
			appointments_to_invoice.append({
				'reference_type': 'Patient Appointment',
				'reference_name': appointment.name,
				'service': service_item,
				'rate': practitioner_charge,
				'income_account': income_account
			})

	return appointments_to_invoice


def get_encounters_to_invoice(patient, company):
	encounters_to_invoice = []
	encounters = frappe.get_list(
		'Patient Encounter',
		fields=['*'],
		filters={'patient': patient.name, 'company': company, 'invoiced': False, 'docstatus': 1}
	)
	if encounters:
		for encounter in encounters:
			if not encounter.appointment:
				practitioner_charge = 0
				income_account = None
				service_item = None
				if encounter.practitioner:
					service_item, practitioner_charge = get_service_item_and_practitioner_charge(encounter)
					income_account = get_income_account(encounter.practitioner, encounter.company)

				encounters_to_invoice.append({
					'reference_type': 'Patient Encounter',
					'reference_name': encounter.name,
					'service': service_item,
					'rate': practitioner_charge,
					'income_account': income_account
				})

	return encounters_to_invoice


def get_lab_tests_to_invoice(patient, company):
	lab_tests_to_invoice = []
	lab_tests = frappe.get_list(
		'Lab Test',
		fields='*',
		filters={'patient': patient.name, 'company': company, 'invoiced': False, 'docstatus': 1}
	)
	for lab_test in lab_tests:
		item, is_billable = frappe.get_cached_value('Lab Test Template', lab_test.template, ['item', 'is_billable'])
		if is_billable:
			if lab_test.insurance_claim:
				if lab_test.claim_status == 'Approved':
					coverage, discount, price_list_rate = frappe.get_cached_value('Healthcare Insurance Claim', lab_test.insurance_claim, ['coverage', 'discount', 'price_list_rate'])
					lab_tests_to_invoice.append({
						'reference_type': 'Lab Test',
						'reference_name': lab_test.name,
						'service': item,
						'rate': price_list_rate,
						'discount_percentage':discount,
						'insurance_claim_coverage': coverage,
						'insurance_claim': lab_test.insurance_claim
					})
			else:
				lab_tests_to_invoice.append({
					'reference_type': 'Lab Test',
					'reference_name': lab_test.name,
					'service': item
				})

	return lab_tests_to_invoice


def get_clinical_procedures_to_invoice(patient, company):
	clinical_procedures_to_invoice = []
	procedures = frappe.get_list(
		'Clinical Procedure',
		fields='*',
		filters={'patient': patient.name, 'company': company, 'invoiced': False}
	)
	for procedure in procedures:
		if not procedure.appointment:
			item, is_billable = frappe.get_cached_value('Clinical Procedure Template', procedure.procedure_template, ['item', 'is_billable'])
			if procedure.procedure_template and is_billable:
				if procedure.insurance_claim:
					if procedure.claim_status == 'Approved':
						coverage, discount, rate = frappe.get_cached_value('Healthcare Insurance Claim', procedure.insurance_claim, ['coverage', 'discount', 'price_list_rate'])
						clinical_procedures_to_invoice.append({
							'reference_type': 'Clinical Procedure',
							'reference_name': procedure.name,
							'service': item,
							'rate': rate,
							'discount_percentage':discount,
							'insurance_claim_coverage': coverage,
							'insurance_claim': procedure.insurance_claim
						})
				else:
					clinical_procedures_to_invoice.append({
						'reference_type': 'Clinical Procedure',
						'reference_name': procedure.name,
						'service': item
					})

		# consumables
		if procedure.invoice_separately_as_consumables and procedure.consume_stock \
			and procedure.status == 'Completed' and not procedure.consumption_invoiced:

			service_item = get_healthcare_service_item('clinical_procedure_consumable_item')
			if not service_item:
				msg = _('Please Configure Clinical Procedure Consumable Item in ')
				msg += '''<b><a href='#Form/Healthcare Settings'>Healthcare Settings</a></b>'''
				frappe.throw(msg, title=_('Missing Configuration'))

			clinical_procedures_to_invoice.append({
				'reference_type': 'Clinical Procedure',
				'reference_name': procedure.name,
				'service': service_item,
				'rate': procedure.consumable_total_amount,
				'description': procedure.consumption_details
			})

	return clinical_procedures_to_invoice


def get_inpatient_services_to_invoice(patient, company):
	services_to_invoice = []
	inpatient_services = frappe.db.sql(
		'''
			SELECT
				io.*
			FROM
				`tabInpatient Record` ip, `tabInpatient Occupancy` io
			WHERE
				ip.patient=%s
				and ip.company=%s
				and io.parent=ip.name
				and io.left=1
				and io.invoiced=0
		''', (patient.name, company), as_dict=1)

	for inpatient_occupancy in inpatient_services:
		service_unit_type = frappe.db.get_value('Healthcare Service Unit', inpatient_occupancy.service_unit, 'service_unit_type')
		service_unit_type = frappe.get_cached_doc('Healthcare Service Unit Type', service_unit_type)
		if service_unit_type and service_unit_type.is_billable:
			hours_occupied = time_diff_in_hours(inpatient_occupancy.check_out, inpatient_occupancy.check_in)
			qty = 0.5
			if hours_occupied > 0:
				actual_qty = hours_occupied / service_unit_type.no_of_hours
				floor = math.floor(actual_qty)
				decimal_part = actual_qty - floor
				if decimal_part > 0.5:
					qty = rounded(floor + 1, 1)
				elif decimal_part < 0.5 and decimal_part > 0:
					qty = rounded(floor + 0.5, 1)
				if qty <= 0:
					qty = 0.5
			services_to_invoice.append({
				'reference_type': 'Inpatient Occupancy',
				'reference_name': inpatient_occupancy.name,
				'service': service_unit_type.item, 'qty': qty
			})

	return services_to_invoice


def get_therapy_sessions_to_invoice(patient, company):
	therapy_sessions_to_invoice = []
	therapy_sessions = frappe.get_list(
		'Therapy Session',
		fields='*',
		filters={'patient': patient.name, 'invoiced': 0, 'company': company}
	)
	for therapy in therapy_sessions:
		if not therapy.appointment:
			if therapy.therapy_type and frappe.db.get_value('Therapy Type', therapy.therapy_type, 'is_billable'):
				therapy_sessions_to_invoice.append({
					'reference_type': 'Therapy Session',
					'reference_name': therapy.name,
					'service': frappe.db.get_value('Therapy Type', therapy.therapy_type, 'item')
				})

	return therapy_sessions_to_invoice

def get_radiology_examinations_to_invoice(patient, company):
	radiology_to_invoice = []
	radiology_examinations = frappe.get_list(
		'Radiology Examination',
		fields='*',
		filters={'patient': patient.name, 'company': company, 'invoiced': False, 'docstatus': 1}
	)
	for radiology_examination in radiology_examinations:
		item, is_billable = frappe.get_cached_value('Radiology Examination Template', radiology_examination.radiology_examination_template, ['item', 'is_billable'])
		if is_billable:
			if radiology_examination.insurance_claim:
				if radiology_examination.claim_status == 'Approved':
					coverage, discount, rate = frappe.get_cached_value('Healthcare Insurance Claim', radiology_examination.insurance_claim, ['coverage', 'discount', 'price_list_rate'])
					radiology_to_invoice.append({
						'reference_type': 'Radiology Examination',
						'reference_name': radiology_examination.name,
						'service': item,
						'rate': rate,
						'discount_percentage':discount,
						'insurance_claim_coverage': coverage,
						'insurance_claim': radiology_examination.insurance_claim
					})
			else:
				radiology_to_invoice.append({
					'reference_type': 'Radiology Examination',
					'reference_name': radiology_examination.name,
					'service': item
				})

	return radiology_to_invoice

def get_healthcare_service_orders_to_invoice(patient, company):
	service_order_to_invoice = []
	service_orders = frappe.get_list(
		'Healthcare Service Order',
		fields='*',
		filters={'patient': patient.name, 'company': company, 'invoiced': False}
	)
	for service_order in service_orders:
		item, is_billable = frappe.get_cached_value(service_order.order_doctype, service_order.order, ['item', 'is_billable'])
		if is_billable:
			if service_order.insurance_claim:
				if service_order.claim_status == 'Approved':
					coverage, discount, rate = frappe.get_cached_value('Healthcare Insurance Claim', service_order.insurance_claim, ['coverage', 'discount', 'price_list_rate'])
					service_order_to_invoice.append({
						'reference_type': 'Healthcare Service Order',
						'reference_name': service_order.name,
						'service': item,
						'rate': rate,
						'qty': service_order.quantity if service_order.quantity else 1,
						'discount_percentage':discount,
						'insurance_claim_coverage': coverage,
						'insurance_claim': service_order.insurance_claim
					})
			else:
				service_order_to_invoice.append({
					'reference_type': 'Healthcare Service Order',
					'reference_name': service_order.name,
					'service': item,
					'qty': service_order.quantity if service_order.quantity else 1
				})
	return service_order_to_invoice

def get_service_item_and_practitioner_charge(doc):
	is_inpatient = doc.inpatient_record
	if is_inpatient:
		service_item = get_practitioner_service_item(doc.practitioner, 'inpatient_visit_charge_item')
		if not service_item:
			service_item = get_appointment_type_service_item(doc.appointment_type, 'inpatient_visit_charge_item')
			if not service_item:
				service_item = get_healthcare_service_item('inpatient_visit_charge_item')

	else:
		service_item = get_practitioner_service_item(doc.practitioner, 'op_consulting_charge_item')
		if not service_item:
			service_item = get_appointment_type_service_item(doc.appointment_type, 'op_consulting_charge_item')
			if not service_item:
				service_item = get_healthcare_service_item('op_consulting_charge_item')
	if not service_item:
		throw_config_service_item(is_inpatient)

	practitioner_charge = get_practitioner_charge(doc.practitioner, is_inpatient)
	if not practitioner_charge:
		throw_config_practitioner_charge(is_inpatient, doc.practitioner)

	return service_item, practitioner_charge


def throw_config_service_item(is_inpatient):
	service_item_label = _('Out Patient Consulting Charge Item')
	if is_inpatient:
		service_item_label = _('Inpatient Visit Charge Item')

	msg = _(('Please Configure {0} in ').format(service_item_label) \
		+ '''<b><a href='#Form/Healthcare Settings'>Healthcare Settings</a></b>''')
	frappe.throw(msg, title=_('Missing Configuration'))


def throw_config_practitioner_charge(is_inpatient, practitioner):
	charge_name = _('OP Consulting Charge')
	if is_inpatient:
		charge_name = _('Inpatient Visit Charge')

	msg = _(('Please Configure {0} for Healthcare Practitioner').format(charge_name) \
		+ ''' <b><a href='#Form/Healthcare Practitioner/{0}'>{0}</a></b>'''.format(practitioner))
	frappe.throw(msg, title=_('Missing Configuration'))


def get_practitioner_service_item(practitioner, service_item_field):
	return frappe.db.get_value('Healthcare Practitioner', practitioner, service_item_field)

def get_appointment_type_service_item(appointment_type, service_item_field):
	return frappe.db.get_value('Appointment Type', appointment_type, service_item_field)

def get_healthcare_service_item(service_item_field):
	return frappe.db.get_single_value('Healthcare Settings', service_item_field)


def get_practitioner_charge(practitioner, is_inpatient):
	if is_inpatient:
		practitioner_charge = frappe.db.get_value('Healthcare Practitioner', practitioner, 'inpatient_visit_charge')
	else:
		practitioner_charge = frappe.db.get_value('Healthcare Practitioner', practitioner, 'op_consulting_charge')
	if practitioner_charge:
		return practitioner_charge
	return False


def manage_invoice_submit_cancel(doc, method):
	if doc.items:
		for item in doc.items:
			if item.get('reference_dt') and item.get('reference_dn'):
				if frappe.get_meta(item.reference_dt).has_field('invoiced'):
					set_invoiced(item, method, doc.name)
			if item.get('insurance_claim'):
				update_insurance_claim(item.insurance_claim, doc.name, doc.posting_date, doc.total)

	if method=='on_submit' and frappe.db.get_single_value('Healthcare Settings', 'create_lab_test_on_si_submit'):
		create_multiple('Sales Invoice', doc.name)


def set_invoiced(item, method, ref_invoice=None):
	invoiced = False
	if method=='on_submit':
		validate_invoiced_on_submit(item)
		invoiced = True

	if item.reference_dt == 'Clinical Procedure':
		if get_healthcare_service_item('clinical_procedure_consumable_item') == item.item_code:
			frappe.db.set_value(item.reference_dt, item.reference_dn, 'consumption_invoiced', invoiced)
		else:
			frappe.db.set_value(item.reference_dt, item.reference_dn, 'invoiced', invoiced)
	else:
		frappe.db.set_value(item.reference_dt, item.reference_dn, 'invoiced', invoiced)

	if item.reference_dt == 'Patient Appointment':
		if frappe.db.get_value('Patient Appointment', item.reference_dn, 'procedure_template'):
			dt_from_appointment = 'Clinical Procedure'
		else:
			dt_from_appointment = 'Patient Encounter'
		manage_doc_for_appointment(dt_from_appointment, item.reference_dn, invoiced)

	elif item.reference_dt == 'Lab Prescription':
		manage_prescriptions(invoiced, item.reference_dt, item.reference_dn, 'Lab Test', 'lab_test_created')

	elif item.reference_dt == 'Procedure Prescription':
		manage_prescriptions(invoiced, item.reference_dt, item.reference_dn, 'Clinical Procedure', 'procedure_created')

	elif item.reference_dt == 'Healthcare Service Order':
		frappe.db.set_value(item.reference_dt, item.reference_dn, 'invoiced', invoiced)

def validate_invoiced_on_submit(item):
	if item.reference_dt == 'Clinical Procedure' and get_healthcare_service_item('clinical_procedure_consumable_item') == item.item_code:
		is_invoiced = frappe.db.get_value(item.reference_dt, item.reference_dn, 'consumption_invoiced')
	else:
		is_invoiced = frappe.db.get_value(item.reference_dt, item.reference_dn, 'invoiced')
	if is_invoiced:
		frappe.throw(_('The item referenced by {0} - {1} is already invoiced'\
		).format(item.reference_dt, item.reference_dn))


def manage_prescriptions(invoiced, ref_dt, ref_dn, dt, created_check_field):
	created = frappe.db.get_value(ref_dt, ref_dn, created_check_field)
	if created:
		# Fetch the doc created for the prescription
		doc_created = frappe.db.get_value(dt, {'prescription': ref_dn})
		frappe.db.set_value(dt, doc_created, 'invoiced', invoiced)


def check_fee_validity(appointment):
	if not frappe.db.get_single_value('Healthcare Settings', 'enable_free_follow_ups'):
		return

	validity = frappe.db.exists('Fee Validity', {
		'practitioner': appointment.practitioner,
		'patient': appointment.patient,
		'valid_till': ('>=', appointment.appointment_date)
	})
	if not validity:
		return

	validity = frappe.get_doc('Fee Validity', validity)
	return validity


def manage_fee_validity(appointment):
	fee_validity = check_fee_validity(appointment)

	if fee_validity:
		if appointment.status == 'Cancelled' and fee_validity.visited > 0:
			fee_validity.visited -= 1
			frappe.db.delete('Fee Validity Reference', {'appointment': appointment.name})
		elif fee_validity.status == 'Completed':
			return
		else:
			fee_validity.visited += 1
			fee_validity.append('ref_appointments', {
				'appointment': appointment.name
			})
		fee_validity.save(ignore_permissions=True)
	else:
		fee_validity = create_fee_validity(appointment)
	return fee_validity


def manage_doc_for_appointment(dt_from_appointment, appointment, invoiced):
	dn_from_appointment = frappe.db.get_value(
		dt_from_appointment,
		filters={'appointment': appointment}
	)
	if dn_from_appointment:
		frappe.db.set_value(dt_from_appointment, dn_from_appointment, 'invoiced', invoiced)


@frappe.whitelist()
def get_drugs_to_invoice(encounter):
	encounter = frappe.get_doc('Patient Encounter', encounter)
	if encounter:
		patient = frappe.get_doc('Patient', encounter.patient)
		if patient:
			if patient.customer:
				items_to_invoice = []
				for drug_line in encounter.drug_prescription:
					if drug_line.drug_code:
						qty = 1
						if frappe.db.get_value('Item', drug_line.drug_code, 'stock_uom') == 'Nos':
							qty = drug_line.get_quantity()

						description = ''
						if drug_line.dosage and drug_line.period:
							description = _('{0} for {1}').format(drug_line.dosage, drug_line.period)

						items_to_invoice.append({
							'drug_code': drug_line.drug_code,
							'quantity': qty,
							'description': description
						})
				return items_to_invoice
			else:
				validate_customer_created(patient)


@frappe.whitelist()
def get_children(doctype, parent, company, is_root=False):
	parent_fieldname = "parent_" + doctype.lower().replace(" ", "_")
	fields = [
		"name as value",
		"is_group as expandable",
		"lft",
		"rgt"
	]
	# fields = [ "name", "is_group", "lft", "rgt" ]
	filters = [["ifnull(`{0}`,'')".format(parent_fieldname), "=", "" if is_root else parent]]

	if is_root:
		fields += ["service_unit_type"] if doctype == "Healthcare Service Unit" else []
		filters.append(["company", "=", company])

	else:
		fields += ["service_unit_type", "allow_appointments", "inpatient_occupancy", "occupancy_status"] if doctype == "Healthcare Service Unit" else []
		fields += [parent_fieldname + " as parent"]

	hc_service_units = frappe.get_list(doctype, fields=fields, filters=filters)

	if doctype == "Healthcare Service Unit":
		for each in hc_service_units:
			occupancy_msg = ""
			if each["expandable"] == 1:
				occupied = False
				vacant = False
				child_list = frappe.db.sql(
					'''
						SELECT
							name, occupancy_status
						FROM
							`tabHealthcare Service Unit`
						WHERE
							inpatient_occupancy = 1
							and lft > %s and rgt < %s
					''', (each['lft'], each['rgt']))

				for child in child_list:
					if not occupied:
						occupied = 0
					if child[1] == "Occupied":
						occupied += 1
					if not vacant:
						vacant = 0
					if child[1] == "Vacant":
						vacant += 1
				if vacant and occupied:
					occupancy_total = vacant + occupied
					occupancy_msg = str(occupied) + " Occupied out of " + str(occupancy_total)
			each["occupied_out_of_vacant"] = occupancy_msg
	return hc_service_units


@frappe.whitelist()
def get_patient_vitals(patient, from_date=None, to_date=None):
	if not patient: return

	vitals = frappe.db.get_all('Vital Signs', filters={
			'docstatus': 1,
			'patient': patient
		}, order_by='signs_date, signs_time', fields=['*'])

	if len(vitals):
		return vitals
	return False


@frappe.whitelist()
def render_docs_as_html(docs):
	# docs key value pair {doctype: docname}
	docs_html = "<div class='col-md-12 col-sm-12 text-muted'>"
	for doc in docs:
		docs_html += render_doc_as_html(doc['doctype'], doc['docname'])['html'] + '<br/>'
		return {'html': docs_html}


@frappe.whitelist()
def render_doc_as_html(doctype, docname, exclude_fields = []):
	#render document as html, three column layout will break
	doc = frappe.get_doc(doctype, docname)
	meta = frappe.get_meta(doctype)
	doc_html = "<div class='col-md-12 col-sm-12'>"
	section_html = ''
	section_label = ''
	html = ''
	sec_on = False
	col_on = 0
	has_data = False
	for df in meta.fields:
		#on section break append append previous section and html to doc html
		if df.fieldtype == "Section Break":
			if has_data and col_on and sec_on:
				doc_html += section_html + html + "</div>"
			elif has_data and not col_on and sec_on:
				doc_html += "<div class='col-md-12 col-sm-12'\
				><div class='col-md-12 col-sm-12'>" \
				+ section_html + html +"</div></div>"
			while col_on:
				doc_html += "</div>"
				col_on -= 1
			sec_on = True
			has_data= False
			col_on = 0
			section_html = ''
			html = ''
			if df.label:
				section_label = df.label
			continue
		#on column break append html to section html or doc html
		if df.fieldtype == "Column Break":
			if sec_on and has_data:
				section_html += "<div class='col-md-12 col-sm-12'\
				><div class='col-md-6 col\
				-sm-6'><b>" + section_label + "</b>" + html + "</div><div \
				class='col-md-6 col-sm-6'>"
			elif has_data:
				doc_html += "<div class='col-md-12 col-sm-12'><div class='col-m\
				d-6 col-sm-6'>" + html + "</div><div class='col-md-6 col-sm-6'>"
			elif sec_on and not col_on:
				section_html += "<div class='col-md-6 col-sm-6'>"
			html = ''
			col_on += 1
			if df.label:
				html += '<br>' + df.label
			continue
		#on table iterate in items and create table based on in_list_view, append to section html or doc html
		if df.fieldtype == 'Table':
			items = doc.get(df.fieldname)
			if not items: continue
			child_meta = frappe.get_meta(df.options)
			if not has_data : has_data = True
			table_head = ''
			table_row = ''
			create_head = True
			for item in items:
				table_row += '<tr>'
				for cdf in child_meta.fields:
					if cdf.in_list_view:
						if create_head:
							table_head += '<th>' + cdf.label + '</th>'
						if item.get(cdf.fieldname):
							table_row += '<td>' + str(item.get(cdf.fieldname)) \
							+ '</td>'
						else:
							table_row += '<td></td>'
				create_head = False
				table_row += '</tr>'
			if sec_on:
				section_html += "<table class='table table-condensed \
				bordered'>" + table_head +  table_row + '</table>'
			else:
				html += "<table class='table table-condensed table-bordered'>" \
				+ table_head +  table_row + "</table>"
			continue
		if df.fieldtype == "Table MultiSelect":
			multiselect_items = doc.get(df.fieldname)
			multitable_meta = frappe.get_meta(df.options)
			if not has_data : has_data = True
			if not multiselect_items: continue
			for m_items in multiselect_items:
				for mdf in multitable_meta.fields:
					html +=  '<br>{0} :&nbsp;{1}'.format(df.label or df.fieldname, m_items.get(mdf.fieldname))
		#on other field types add label and value to html
		if not df.hidden and not df.print_hide and doc.get(df.fieldname) and df.fieldname not in exclude_fields:
			html +=  '<br>{0} : {1}'.format(df.label or df.fieldname, \
			doc.get(df.fieldname))
			if not has_data : has_data = True
	if sec_on and col_on and has_data:
		doc_html += section_html + html + '</div></div>'
	elif sec_on and not col_on and has_data:
		doc_html += "<div class='col-md-12 col-sm-12'\
		><div class='col-md-12 col-sm-12'>" \
		+ section_html + html +'</div></div>'
	if doc_html:
		doc_html = "<div class='small'><div class='col-md-12 text-right'><a class='btn btn-default btn-xs' href='#Form/%s/%s'></a></div>" %(doctype, docname) + doc_html + '</div>'
	return {'html': doc_html}


def update_address_link(address, method):
	# Healthcare Service Invoice.
	domain_settings = frappe.get_doc('Domain Settings')
	active_domains = [d.domain for d in domain_settings.active_domains]

	if "Healthcare" in active_domains:
		address_patient = None
		for link in address.links:
			if link.link_doctype == 'Patient':
				address_patient = link.link_name
		if address_patient:
			customer = frappe.db.get_value('Patient', address_patient, 'customer')
			if not address.has_link('Customer', customer):
				address.append('links', dict(link_doctype = 'Customer', link_name = customer))
				address.save()

def create_item_from_doc(doc, item_name):
	if(doc.is_billable == 1):
		disabled = 0
	else:
		disabled = 1
	#insert item
	item =  frappe.get_doc({
	'doctype': 'Item',
	'item_code': doc.item_code,
	'item_name': item_name,
	'item_group': doc.item_group,
	'description': doc.description,
	'is_sales_item': 1,
	'is_service_item': 1,
	'is_purchase_item': 0,
	'is_stock_item': 0,
	'show_in_website': 0,
	'is_pro_applicable': 0,
	'disabled': disabled,
	'stock_uom': 'Unit'
	}).insert(ignore_permissions=True)

	#insert item price
	#get item price list to insert item price
	if(doc.rate != 0.0):
		price_list_name = frappe.db.get_value('Selling Settings', None, 'selling_price_list')
		if not price_list_name:
			price_list_name = frappe.db.get_value('Price List', {'selling': 1})
		if price_list_name:
			if(doc.rate):
				make_item_price(item.name, price_list_name, doc.rate)
			else:
				make_item_price(item.name, price_list_name, 0.0)
	#Set item to the template
	frappe.db.set_value(doc.doctype, doc.name, 'item', item.name)

	doc.reload() #refresh the doc after insert.

def make_item_price(item, price_list_name, item_price):
	frappe.get_doc({
		'doctype': 'Item Price',
		'price_list': price_list_name,
		'item_code': item,
		'price_list_rate': item_price
	}).insert(ignore_permissions=True)

def update_item_from_doc(doc, item_name):
	if(doc.is_billable == 1 and doc.item):
		updating_item(doc, item_name)
		if(doc.rate != 0.0):
			updating_rate(doc, item_name)
	elif(doc.is_billable == 0 and doc.item):
		frappe.db.set_value('Item', doc.item, 'disabled', 1)

def updating_item(doc, item_name):
	frappe.db.sql(
		'''
			UPDATE
				`tabItem`
			SET
				item_name=%s, item_group=%s, disabled=0,
				description=%s, modified=NOW()
			WHERE
				 item_code=%s''',
			(item_name, doc.item_group , doc.description, doc.item))

def updating_rate(doc, item_name):
	frappe.db.sql(
		'''
			UPDATE
				`tabItem Price`
			SET
				item_name=%s, price_list_rate=%s, modified=NOW()
			WHERE
				item_code=%s''',
			(item_name, doc.rate, doc.item))

def on_trash_doc_having_item_reference(doc):
	if(doc.item):
		try:
			frappe.delete_doc('Item',doc.item)
		except Exception:
			frappe.throw(_('Not permitted. Please disable the {0}').format(doc.doctype))

@frappe.whitelist()
def manage_healthcare_doc_cancel(doc):
	if frappe.get_meta(doc.doctype).has_field("invoiced"):
		if doc.invoiced and get_sales_invoice_for_healthcare_doc(doc.doctype, doc.name):
			frappe.throw(_("Can not cancel invoiced {0}").format(doc.doctype))
	check_if_healthcare_doc_is_linked(doc, "Cancel")
	delete_medical_record(doc.doctype, doc.name)

def check_if_healthcare_doc_is_linked(doc, method):
	item_linked = {}
	exclude_docs = ['Patient Medical Record']
	from frappe.desk.form.linked_with import get_linked_doctypes, get_linked_docs
	linked_docs = get_linked_docs(doc.doctype, doc.name, linkinfo=get_linked_doctypes(doc.doctype))
	for linked_doc in linked_docs:
		if linked_doc not in exclude_docs:
			for linked_doc_obj in linked_docs[linked_doc]:
				if method == "Cancel" and linked_doc_obj.docstatus < 2:
					if linked_doc in item_linked:
						item_linked[linked_doc].append(linked_doc_obj.name)
					else:
						item_linked[linked_doc] = [linked_doc_obj.name]
	if item_linked:
		msg = ""
		for doctype in item_linked:
			msg += doctype+"("
			for docname in item_linked[doctype]:
				msg += '<a href="#Form/{0}/{1}">{1}</a>, '.format(doctype, docname)
			msg  = msg[:-2]
			msg += "), "
		msg  = msg[:-2]
		frappe.throw(_('Cannot delete or cancel because {0} {1} is linked with {2}')
			.format(doc.doctype, doc.name, msg), frappe.LinkExistsError)

def delete_medical_record(reference_doc, reference_name):
	query = """
		delete from
			`tabPatient Medical Record`
		where
			reference_doctype = %s and reference_name = %s"""
	frappe.db.sql(query, (reference_doc, reference_name))

# make_healthcare_service_order
@frappe.whitelist()
def make_healthcare_service_order(args):
	healthcare_service_order = frappe.new_doc('Healthcare Service Order')
	for key in args:
		if key == 'order_date':
			healthcare_service_order.set(key, getdate(args[key]))
		elif key == 'expected_date':
			healthcare_service_order.set(key, getdate(args[key]))
		else:
			healthcare_service_order.set(key, args[key] if args[key] else '')
	healthcare_service_order.save(ignore_permissions=True)
#insurance claim
def create_insurance_claim(doc, service_doctype, service, qty, billing_item):
	insurance_details = get_insurance_details(service, doc.insurance_subscription, billing_item)
	insurance_claim = frappe.new_doc('Healthcare Insurance Claim')
	insurance_claim.patient = doc.patient
	insurance_claim.reference_dt = doc.doctype
	insurance_claim.reference_dn = doc.name
	insurance_claim.insurance_subscription = doc.insurance_subscription
	insurance_claim.insurance_company = doc.insurance_company
	insurance_claim.healthcare_service_type = service_doctype
	insurance_claim.service_template = service
	insurance_claim.claim_status = 'Approved' if insurance_details.is_auto_approval else 'Pending'
	insurance_claim.mode_of_claim_approval = 'Automatic' if insurance_details.is_auto_approval else ''
	insurance_claim.claim_posting_date = nowdate()
	insurance_claim.quantity = qty
	insurance_claim.service_doctype = doc.doctype
	insurance_claim.service_item = billing_item
	insurance_claim.discount = insurance_details.discount
	insurance_claim.price_list_rate = insurance_details.rate
	insurance_claim.amount = float(insurance_details.rate) * float(qty)
	if insurance_claim.discount and float(insurance_claim.discount) > 0:
		insurance_claim.discount_amount = float(insurance_claim.price_list_rate) * float(insurance_claim.discount) * 0.01
		insurance_claim.amount = float(insurance_details.rate - insurance_claim.discount_amount) * float(qty)
	insurance_claim.coverage = insurance_details.coverage
	insurance_claim.coverage_amount = float(insurance_claim.amount) * 0.01 * float(insurance_claim.coverage)
	insurance_claim.save(ignore_permissions=True)
	insurance_claim.submit()
	return insurance_claim.name , insurance_claim.claim_status

def get_insurance_details(service, insurance_subscription, billing_item):
	valid_date = nowdate()
	claim_coverage = 0
	price_list_rate = 0
	claim_discount = 0
	insurance_subscription = frappe.get_doc('Healthcare Insurance Subscription', insurance_subscription)
	if insurance_subscription and valid_insurance(insurance_subscription.name, insurance_subscription.insurance_company, valid_date):
		if insurance_subscription.healthcare_insurance_coverage_plan:
			price_list_rate = get_insurance_price_list_rate(insurance_subscription.healthcare_insurance_coverage_plan, billing_item)
			coverage, discount, is_auto_approval = get_insurance_coverage_details(insurance_subscription.healthcare_insurance_coverage_plan, service)
			if coverage and discount:
				claim_discount = discount
				claim_coverage = coverage
	insurance_details = frappe._dict({'rate': price_list_rate, 'discount': claim_discount, 'coverage': claim_coverage, 'is_auto_approval': is_auto_approval})
	return insurance_details

def valid_insurance(insurance_subscription, insurance_company, posting_date):
	if frappe.db.exists('Healthcare Insurance Contract',
		{
			'insurance_company': insurance_company,
			'start_date':("<=", getdate(posting_date)),
			'end_date':(">=", getdate(posting_date)),
			'is_active': 1
		}):
		if frappe.db.exists('Healthcare Insurance Subscription',
			{
				'name': insurance_subscription,
				'subscription_end_date':(">=", getdate(posting_date)),
				'is_active': 1
			}):
			return True
	return False

def get_insurance_price_list_rate(healthcare_insurance_coverage_plan, billing_item):
	rate = 0.0
	if healthcare_insurance_coverage_plan:
		price_list = frappe.db.get_value('Healthcare Insurance Coverage Plan', healthcare_insurance_coverage_plan, 'price_list')
		if price_list:
			item_price = frappe.db.exists('Item Price',
						{
							'item_code': billing_item,
							'price_list': price_list
						})
			if item_price:
				rate = frappe.db.get_value('Item Price', item_price, 'price_list_rate')
	return rate

def get_insurance_coverage_details(healthcare_insurance_coverage_plan, service):
	coverage = 0
	discount = 0
	is_auto_approval = True
	if healthcare_insurance_coverage_plan:
		healthcare_service_coverage = frappe.db.exists('Healthcare Service Insurance Coverage',
									{
										'healthcare_insurance_coverage_plan': healthcare_insurance_coverage_plan,
										'healthcare_service_template': service
									})
		if healthcare_service_coverage:
			coverage, discount = frappe.db.get_value('Healthcare Service Insurance Coverage', healthcare_service_coverage, ['coverage', 'discount'])
			approval_mandatory_for_claim = frappe.db.get_value('Healthcare Service Insurance Coverage', healthcare_service_coverage, 'approval_mandatory_for_claim')
			if approval_mandatory_for_claim:
				manual_approval_only = frappe.db.get_value('Healthcare Service Insurance Coverage', healthcare_service_coverage, 'manual_approval_only')
				if manual_approval_only:
					is_auto_approval = False
			return coverage, discount, is_auto_approval
def update_insurance_claim(insurance_claim,sales_invoice_name, posting_date, total_amount):
	frappe.set_value('Healthcare Insurance Claim', insurance_claim, 'sales_invoice', sales_invoice_name)
	frappe.set_value('Healthcare Insurance Claim', insurance_claim, 'sales_invoice_posting_date', posting_date)
	frappe.set_value('Healthcare Insurance Claim', insurance_claim, 'billing_date', nowdate())
	frappe.set_value('Healthcare Insurance Claim', insurance_claim, 'billing_amount', total_amount)
