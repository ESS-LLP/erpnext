# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe import _
import datetime
import math
from frappe.utils import today, now_datetime, getdate, time_diff_in_hours, get_datetime, add_to_date, rounded, flt
from frappe.model.document import Document
from frappe.desk.reportview import get_match_cond
from erpnext.healthcare.utils import sales_item_details_for_healthcare_doc, get_insurance_details
from erpnext.healthcare.doctype.healthcare_settings.healthcare_settings import get_receivable_account, get_account

class InpatientRecord(Document):
	def after_insert(self):
		frappe.db.set_value("Patient", self.patient, "inpatient_status", "Admission Scheduled")
		frappe.db.set_value("Patient", self.patient, "inpatient_record", self.name)

	def validate(self):
		self.validate_already_scheduled_or_admitted()
		if self.status == "Discharged":
			frappe.db.set_value("Patient", self.patient, "inpatient_status", None)
			frappe.db.set_value("Patient", self.patient, "inpatient_record", None)

	def validate_already_scheduled_or_admitted(self):
		query = """
			select name, status
			from `tabInpatient Record`
			where (status = 'Admitted' or status = 'Admission Scheduled')
			and name != %(name)s and patient = %(patient)s
			"""

		ip_record = frappe.db.sql(query,{
				"name": self.name,
				"patient": self.patient
			}, as_dict = 1)

		if ip_record:
			msg = _(("Already {0} Patient {1} with Inpatient Record ").format(ip_record[0].status, self.patient) \
				+ """ <b><a href="#Form/Inpatient Record/{0}">{0}</a></b>""".format(ip_record[0].name))
			frappe.throw(msg)

	def admit(self, service_unit, check_in, expected_discharge=None):
		admit_patient(self, service_unit, check_in, expected_discharge)

	def discharge(self):
		self.submit_all_invoices()
		discharge_patient(self)

	def transfer(self, service_unit, check_in, leave_from, requested_transfer=False):
		if leave_from:
			patient_leave_service_unit(self, check_in, leave_from)
		if service_unit:
			transfer_patient(self, service_unit, check_in)
		if requested_transfer:
			self.transfer_requested = False
			self.transfer_requested_unit_type = None
			self.expected_transfer = None
			self.status = "Admitted"
			self.save(ignore_permissions = True)
			frappe.db.set_value("Patient", self.patient, "inpatient_status", "Admitted")

	def submit_all_invoices(self):
		submit_all_ip_invoices(self.name)

	def get_inpatient_invoice_details(self):
		sales_invoice_list = []
		group_wise_item_total = {}
		group_wise_item_dict = {}
		for si in frappe.get_list('Sales Invoice', {'inpatient_record': self.name, 'docstatus': 1}):
			si_obj = frappe.get_doc("Sales Invoice", si.name)
			sales_invoice_list.append(si_obj)
			for item in si_obj.items:
				item_group = get_item_group_as_group(item.item_code)
				if not item_group in group_wise_item_dict:
					group_wise_item_dict[item_group] = [item]
					group_wise_item_total[item_group] = {"amount": item.amount}
				else:
					group_wise_item_dict[item_group].append(item)
					data = group_wise_item_total[item_group]
					group_wise_item_total[item_group] = {"amount": data['amount']+item.amount}
		return sales_invoice_list, group_wise_item_dict, group_wise_item_total

	def create_payment_entry(self, paid_amount=None):
		payment_entry = frappe.new_doc('Payment Entry')
		payment_entry.voucher_type = 'Payment Entry'
		payment_entry.company = self.company
		payment_entry.posting_date =  today()
		payment_entry.payment_type="Receive"
		payment_entry.party_type="Customer"
		payment_entry.party = frappe.get_value("Patient", self.patient, "customer")
		payment_entry.patient=self.patient
		payment_entry.paid_amount=paid_amount if paid_amount else self.total_standard_selling_rate
		payment_entry.setup_party_account_field()
		payment_entry.set_missing_values()
		return payment_entry.as_dict()

	def get_billing_info(self):
		return get_ip_billing_info(self)

@frappe.whitelist()
def get_ip_billing_info(doc):
	customer = frappe.db.get_value("Patient", doc.patient, 'customer')

	ip_grand_total = frappe.get_all("Sales Invoice",
		filters={
			'docstatus': 1,
			'customer': customer,
			'inpatient_record': doc.name
		},
		fields=["patient", "sum(grand_total) as grand_total", "sum(base_grand_total) as base_grand_total"]
	)

	ip_grand_total_unpaid = frappe.get_all("Sales Invoice",
		filters={
			'docstatus': 1,
			'customer': customer,
			'inpatient_record': doc.name,
			'status': ['not in', 'Paid']
		},
		fields=["patient", "sum(grand_total) as grand_total", "sum(base_grand_total) as base_grand_total"]
	)

	company_default_currency = frappe.db.get_value("Company", doc.company, 'default_currency')
	from erpnext.accounts.party import get_party_account_currency
	party_account_currency = get_party_account_currency("Customer", customer, doc.company)

	if party_account_currency==company_default_currency:
		billing_this_year = flt(ip_grand_total[0]["base_grand_total"])
		total_unpaid = flt(ip_grand_total_unpaid[0]["base_grand_total"])
	else:
		billing_this_year = flt(ip_grand_total[0]["grand_total"])
		total_unpaid = flt(ip_grand_total_unpaid[0]["grand_total"])

	info = {}
	info["total_billing"] = flt(billing_this_year) if billing_this_year else 0
	info["currency"] = party_account_currency
	info["total_unpaid"] = flt(total_unpaid) if total_unpaid else 0
	return info

def get_item_group_as_group(item_code):
	item_group = frappe.get_value("Item", item_code, "item_group")
	is_group = frappe.get_value("Item Group", item_group, "is_group")
	if is_group:
		return item_group
	else:
		return frappe.get_value("Item Group", item_group, "parent_item_group")

def submit_all_ip_invoices(ip):
	for si in frappe.get_list('Sales Invoice', {'inpatient_record': ip, 'docstatus': 0}):
		if si and si.name:
			frappe.get_doc("Sales Invoice", si.name).submit()

@frappe.whitelist()
def schedule_inpatient(args):
	dialog = json.loads(args)
	inpatient_record = frappe.new_doc('Inpatient Record')
	# Set Patient Details
	set_ip_admission_patient_details(inpatient_record, dialog)
	# Set Inpatient Record Details
	set_ip_admission_record_details(inpatient_record, dialog)
	# Set Inpatient Record Child
	encounter = frappe.get_doc("Patient Encounter", dialog['encounter_id'])
	# Medication
	if encounter and encounter.drug_prescription:
		set_ip_admission_child_records(inpatient_record, "drug_prescription", encounter.drug_prescription)
	# Investigations
	if encounter and encounter.lab_test_prescription:
		set_ip_admission_child_records(inpatient_record, "lab_test_prescription", encounter.lab_test_prescription)
	# Procedure Prescription
	if encounter and encounter.procedure_prescription:
		set_ip_admission_child_records(inpatient_record, "inpatient_record_procedure", encounter.procedure_prescription)
	inpatient_record.save(ignore_permissions = True)

def set_ip_admission_child_records(inpatient_record, table_name, encounter_table):
	for item in  encounter_table:
		table = inpatient_record.append(table_name)
		for df in table.meta.get("fields"):
			table.set(df.fieldname, item.get(df.fieldname))
		if(table_name == "inpatient_record_procedure"):
			table.set("prescription", item.get("name"))

def set_ip_admission_patient_details(inpatient_record, dialog):
	patient_obj = frappe.get_doc('Patient', dialog['patient'])
	inpatient_record.patient = dialog['patient']
	inpatient_record.patient_name = patient_obj.patient_name
	inpatient_record.gender = patient_obj.sex
	inpatient_record.blood_group = patient_obj.blood_group
	inpatient_record.dob = patient_obj.dob
	inpatient_record.mobile = patient_obj.mobile
	inpatient_record.email = patient_obj.email
	inpatient_record.phone = patient_obj.phone
	return inpatient_record

def set_ip_admission_record_details(inpatient_record, dialog):
	inpatient_record.status = "Admission Scheduled"
	inpatient_record.scheduled_date = today()
	inpatient_record.ordering_practitioner = dialog['ref_practitioner']
	inpatient_record.referring_encounter = dialog['encounter_id']
	encounter = frappe.get_doc("Patient Encounter", dialog['encounter_id'])
	if encounter.source:
		inpatient_record.source=encounter.source
	if encounter.referring_practitioner:
		inpatient_record.referring_practitioner=encounter.referring_practitioner
	inpatient_record.medical_department = dialog['medical_department']
	inpatient_record.primary_practitioner = dialog['primary_practitioner']
	inpatient_record.secondary_practitioner = dialog['secondary_practitioner']
	inpatient_record.admission_ordered_for = dialog['admission_ordered_for']
	inpatient_record.chief_complaint = dialog['chief_complaint']
	inpatient_record.diagnosis = dialog['diagnosis']
	inpatient_record.admission_service_unit_type = dialog['service_unit_type']
	inpatient_record.expected_length_of_stay = dialog['expected_length_of_stay']
	inpatient_record.admission_instruction = dialog['admission_instruction']
	inpatient_record.allowed_total_credit_coverage = dialog['allowed_total_credit_coverage']
	return inpatient_record

@frappe.whitelist()
def schedule_discharge(args):
	dialog = json.loads(args)
	inpatient_record_id = frappe.db.get_value('Patient', dialog['patient'], 'inpatient_record')
	if inpatient_record_id:
		inpatient_record = frappe.get_doc("Inpatient Record", inpatient_record_id)
		set_ip_discharge_details(inpatient_record, dialog)
		check_out_inpatient(inpatient_record)

		inpatient_record.save(ignore_permissions = True)
	frappe.db.set_value("Patient", dialog['patient'], "inpatient_status", "Discharge Scheduled")

def set_ip_discharge_details(inpatient_record, dialog):
	inpatient_record.discharge_practitioner = dialog['discharge_practitioner']
	inpatient_record.discharge_encounter = dialog['encounter_id']
	inpatient_record.discharge_ordered_for = dialog['discharge_ordered']
	inpatient_record.followup_date = dialog['followup_date']
	inpatient_record.discharge_instruction = dialog['discharge_instruction']
	inpatient_record.discharge_note = dialog['discharge_note']
	inpatient_record.include_chief_complaint = dialog['include_chief_complaint']
	inpatient_record.include_diagnosis = dialog['include_diagnosis']
	inpatient_record.include_medication = dialog['include_medication']
	inpatient_record.include_investigations = dialog['include_investigations']
	inpatient_record.include_procedures = dialog['include_procedures']
	inpatient_record.include_occupancy_details = dialog['include_occupancy_details']
	inpatient_record.status = "Discharge Scheduled"

def check_out_inpatient(inpatient_record):
	if inpatient_record.inpatient_occupancies:
		for inpatient_occupancy in inpatient_record.inpatient_occupancies:
			if inpatient_occupancy.left != 1:
				inpatient_occupancy.left = True
				inpatient_occupancy.check_out = now_datetime()
				invoice_ip_occupancy()
				frappe.db.set_value("Healthcare Service Unit", inpatient_occupancy.service_unit, "status", get_check_out_stats())

def discharge_patient(inpatient_record):
	validate_invoiced_inpatient(inpatient_record)
	inpatient_record.discharge_date = today()
	inpatient_record.status = "Discharged"

	inpatient_record.save(ignore_permissions = True)

def validate_invoiced_inpatient(inpatient_record):
	pending_invoices = []
	if inpatient_record.inpatient_occupancies:
		service_unit_names = False
		for inpatient_occupancy in inpatient_record.inpatient_occupancies:
			if inpatient_occupancy.invoiced != 1:
				if service_unit_names:
					service_unit_names += ", " + inpatient_occupancy.service_unit
				else:
					service_unit_names = inpatient_occupancy.service_unit
		if service_unit_names:
			pending_invoices.append("Inpatient Occupancy (" + service_unit_names + ")")

	docs = ["Patient Appointment", "Patient Encounter", "Lab Test", "Clinical Procedure"]

	for doc in docs:
		doc_name_list = get_inpatient_docs_not_invoiced(doc, inpatient_record)
		if doc_name_list:
			pending_invoices = get_pending_doc(doc, doc_name_list, pending_invoices)

	if pending_invoices:
		frappe.throw(_("Can not mark Inpatient Record Discharged, there are Unbilled Invoices {0}").format(", "
			.join(pending_invoices)))

def get_pending_doc(doc, doc_name_list, pending_invoices):
	if doc_name_list:
		doc_ids = False
		for doc_name in doc_name_list:
			if doc_ids:
				doc_ids += ", "+doc_name.name
			else:
				doc_ids = doc_name.name
		if doc_ids:
			pending_invoices.append(doc + " (" + doc_ids + ")")

	return pending_invoices

def get_inpatient_docs_not_invoiced(doc, inpatient_record):
	return frappe.db.get_list(doc, filters = {"patient": inpatient_record.patient,
					"inpatient_record": inpatient_record.name, "invoiced": 0})

def admit_patient(inpatient_record, service_unit, check_in, expected_discharge=None):
	inpatient_record.admitted_datetime = check_in
	inpatient_record.status = "Admitted"
	inpatient_record.expected_discharge = expected_discharge

	inpatient_record.set('inpatient_occupancies', [])
	transfer_patient(inpatient_record, service_unit, check_in)

	frappe.db.set_value("Patient", inpatient_record.patient, "inpatient_status", "Admitted")
	frappe.db.set_value("Patient", inpatient_record.patient, "inpatient_record", inpatient_record.name)

def transfer_patient(inpatient_record, service_unit, check_in):
	item_line = inpatient_record.append('inpatient_occupancies', {})
	item_line.service_unit = service_unit
	item_line.check_in = check_in

	inpatient_record.save(ignore_permissions = True)

	frappe.db.set_value("Healthcare Service Unit", service_unit, "status", "Occupied")

def patient_leave_service_unit(inpatient_record, check_out, leave_from):
	if inpatient_record.inpatient_occupancies:
		for inpatient_occupancy in inpatient_record.inpatient_occupancies:
			if inpatient_occupancy.left != 1 and inpatient_occupancy.service_unit == leave_from:
				inpatient_occupancy.left = True
				inpatient_occupancy.check_out = check_out
				frappe.db.set_value("Healthcare Service Unit", inpatient_occupancy.service_unit, "status", get_check_out_stats())
	inpatient_record.save(ignore_permissions = True)

@frappe.whitelist()
def get_leave_from(doctype, txt, searchfield, start, page_len, filters):
	docname = filters['docname']

	query = '''select io.service_unit
		from `tabInpatient Occupancy` io, `tabInpatient Record` ir
		where io.parent = '{docname}' and io.parentfield = 'inpatient_occupancies'
		and io.left!=1 and io.parent = ir.name'''

	return frappe.db.sql(query.format(**{
		"docname":	docname,
		"searchfield":	searchfield,
		"mcond":	get_match_cond(doctype)
	}), {
		'txt': "%%%s%%" % txt,
		'_txt': txt.replace("%", ""),
		'start': start,
		'page_len': page_len
	})

@frappe.whitelist()
def transfer_order(patient, transfer_unit_type, expected_transfer=None):
	inpatient_record_id = frappe.db.get_value('Patient', patient, 'inpatient_record')
	if inpatient_record_id:
		inpatient_record = frappe.get_doc("Inpatient Record", inpatient_record_id)
		inpatient_record.transfer_requested = True
		inpatient_record.transfer_requested_unit_type = transfer_unit_type
		inpatient_record.expected_transfer = expected_transfer
		inpatient_record.status = "Transfer Scheduled"
		inpatient_record.save(ignore_permissions = True)
		frappe.db.set_value("Patient", patient, "inpatient_status", "Transfer Scheduled")

@frappe.whitelist()
def get_check_out_stats():
	default_check_out_status = frappe.db.get_value("Healthcare Settings", None, "healthcare_service_unit_checkout_status")
	if not default_check_out_status:
		return "Vacant"
	return default_check_out_status

@frappe.whitelist()
def invoice_ip_occupancy():
	if frappe.db.get_value("Healthcare Settings", None, "auto_invoice_inpatient") == '1':
		auto_invoice_time = datetime.datetime.strptime(frappe.get_value("Healthcare Settings", None, "ip_service_unit_checkout_time"), "%H:%M:%S")
		auto_invoice_dt = add_to_date(getdate(), hours=auto_invoice_time.hour, minutes=auto_invoice_time.minute,
			seconds=auto_invoice_time.second)
		fields = ["name", "service_unit", "check_in", "left", "check_out", "invoiced_to", "invoiced", "auto_invoiced", "parent"]
		query = """
			select
				*
			from
				`tabInpatient Occupancy`
			where
				invoiced != 1
		"""
		ip_occupancies = frappe.db.sql(query, as_dict=True)
		for ipo in ip_occupancies:
			check_in_dt = ipo.check_in
			if ipo.auto_invoiced and ipo.invoiced_to:
				check_in_dt = ipo.invoiced_to
			# if(get_datetime(auto_invoice_dt) >= get_datetime(check_in_dt) or (ipo.check_out and ipo.left == '1')):
			if(get_datetime(auto_invoice_dt) >= get_datetime(check_in_dt)):
				service_unit_type = frappe.get_doc("Healthcare Service Unit Type", frappe.db.get_value("Healthcare Service Unit", ipo.service_unit, "service_unit_type"))
				if service_unit_type and service_unit_type.is_billable == 1:
					ip = frappe.get_doc("Inpatient Record", ipo.parent)
					sales_invoice = frappe.new_doc("Sales Invoice")
					sales_invoice.patient = ip.patient
					sales_invoice.patient_name = ip.patient_name
					sales_invoice.customer = frappe.get_value("Patient", ip.patient, "customer")
					sales_invoice.ref_practitioner = ip.primary_practitioner
					sales_invoice.due_date = getdate()
					sales_invoice.inpatient_record = ip.name
					sales_invoice.company = ip.company
					sales_invoice.debit_to = get_receivable_account(ip.company, ip.patient)
					update_ip_occupancy_invoice(sales_invoice, ipo, service_unit_type, check_in_dt, ip)

def update_ip_occupancy_invoice(sales_invoice, inpatient_occupancy, service_unit_type, check_in_dt, ip):
	unit_in_no_of_hours = 0
	if service_unit_type.no_of_hours and service_unit_type.no_of_hours > 0:
		unit_in_no_of_hours = service_unit_type.no_of_hours
	# if inpatient_occupancy.check_out and ipo.left == '1':
	# 	check_out = inpatient_occupancy.check_out
	check_out = get_datetime(check_in_dt) + datetime.timedelta(hours=unit_in_no_of_hours)
	hours_occupied = time_diff_in_hours(check_out, check_in_dt)
	qty = 0.5
	if hours_occupied > 0:
		if service_unit_type.no_of_hours and service_unit_type.no_of_hours > 0:
			actual_qty = hours_occupied / service_unit_type.no_of_hours
		else:
			# 24 hours = 1 Day
			actual_qty = hours_occupied / 24
		floor = math.floor(actual_qty)
		decimal_part = actual_qty - floor
		if decimal_part > 0.5:
			qty = rounded(floor + 1, 1)
		elif decimal_part < 0.5 and decimal_part > 0:
			qty = rounded(floor + 0.5, 1)
		if qty <= 0:
			qty = 0.5
	item_line = sales_invoice.append("items")
	item_line.item_code = service_unit_type.item
	item_details = sales_item_details_for_healthcare_doc(service_unit_type.item, ip)
	item_line.item_name = item_details.item_name
	item_line.description = frappe.db.get_value("Item", item_line.item_code, "description")
	item_line.reference_dt = "Inpatient Occupancy"
	item_line.reference_dn = inpatient_occupancy.name
	item_line.rate = item_details.price_list_rate
	if ip.insurance and item_line.item_code:
		insurance_details = get_insurance_details(ip.insurance, item_line.item_code)
		if insurance_details and insurance_details.rate:
			item_line.rate = insurance_details.rate - (insurance_details.rate*0.01*insurance_details.discount)
			item_line.insurance_claim_coverage = insurance_details.coverage
	item_line.qty = qty
	item_line.amount = item_line.rate * item_line.qty
	if ip.insurance and item_line.insurance_claim_coverage and float(item_line.insurance_claim_coverage) > 0:
		item_line.insurance_claim_amount = item_line.amount*0.01*float(item_line.insurance_claim_coverage)
		sales_invoice.total_insurance_claim_amount = item_line.insurance_claim_amount
	sales_invoice.set_missing_values(for_validate = True)

	sales_invoice.save(ignore_permissions=True)
	sales_invoice.submit()
	ipo = frappe.get_doc("Inpatient Occupancy", inpatient_occupancy.name)
	ipo.auto_invoiced = True
	ipo.invoiced_to = get_datetime(check_out)
	ipo.save()
	return sales_invoice

@frappe.whitelist()
def book_all_appointments(appointments_table, inpatient_record):
	appointments_table = json.loads(appointments_table)
	for appointment in appointments_table:
		new_appointment = frappe.new_doc("Patient Appointment")
		for key in appointment:
			new_appointment.set(key, appointment[key] if appointment[key] else '')
		new_appointment.status = "Scheduled"
		inpatient_record = frappe.get_doc("Inpatient Record", inpatient_record)
		new_appointment.source = inpatient_record.source
		if inpatient_record.referring_practitioner:
			new_appointment.referring_practitioner = inpatient_record.referring_practitioner
		new_appointment.save(ignore_permissions = True)
		frappe.msgprint(_("Appointment booked"), alert=True)

@frappe.whitelist()
def create_delivery_note(ip_record, item, qty, s_wh):
	delivery_note = frappe.new_doc("Delivery Note")
	doc = frappe.get_doc("Inpatient Record", ip_record)
	delivery_note.company = doc.company
	delivery_note.patient = doc.patient
	delivery_note.patient_name = frappe.db.get_value("Patient", doc.patient, "patient_name")
	delivery_note.customer = frappe.db.get_value("Patient", doc.patient, "customer")
	delivery_note.inpatient_record = ip_record
	delivery_note.set_warehouse = s_wh
	expense_account = get_account(None, "expense_account", "Healthcare Settings", doc.company)

	child = delivery_note.append('items')
	item_details = sales_item_details_for_healthcare_doc(item, doc)
	child.item_code = item
	child.item_name = item_details.item_name
	child.uom = item_details.uom
	child.stock_uom = item_details.stock_uom
	child.qty = flt(qty)
	child.warehouse = s_wh
	cost_center = frappe.get_cached_value('Company',  doc.company,  'cost_center')
	child.cost_center = cost_center
	#if not expense_account:
	#	expense_account = frappe.db.get_value("Item", item_line.item_code, "expense_account")
	child.expense_account = expense_account
	child.description = frappe.db.get_value("Item", item, "description")
	child.rate = item_details.price_list_rate
	child.price_list_rate = item_details.price_list_rate
	child.amount = item_details.price_list_rate * child.qty

	delivery_note.insert(ignore_permissions = True)
	delivery_note.submit()
