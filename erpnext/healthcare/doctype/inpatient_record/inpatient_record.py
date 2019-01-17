# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe import _
from frappe.utils import today, now_datetime
from frappe.model.document import Document
from frappe.desk.reportview import get_match_cond

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
		set_ip_admission_child_records(inpatient_record, "procedure_prescription", encounter.procedure_prescription)

	inpatient_record.save(ignore_permissions = True)

def set_ip_admission_child_records(inpatient_record, table_name, encounter_table):
	for item in  encounter_table:
		table = inpatient_record.append(table_name)
		for df in table.meta.get("fields"):
			table.set(df.fieldname, item.get(df.fieldname))

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
	inpatient_record.referring_practitioner = dialog['ref_practitioner']
	inpatient_record.referring_encounter = dialog['encounter_id']
	inpatient_record.medical_department = dialog['medical_department']
	inpatient_record.primary_practitioner = dialog['primary_practitioner']
	inpatient_record.secondary_practitioner = dialog['secondary_practitioner']
	inpatient_record.admission_ordered_for = dialog['admission_ordered_for']
	inpatient_record.chief_complaint = dialog['chief_complaint']
	inpatient_record.diagnosis = dialog['diagnosis']
	inpatient_record.admission_service_unit_type = dialog['service_unit_type']
	inpatient_record.expected_length_of_stay = dialog['expected_length_of_stay']
	inpatient_record.admission_instruction = dialog['admission_instruction']
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
				frappe.db.set_value("Healthcare Service Unit", inpatient_occupancy.service_unit, "status", "Vacant")

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
				frappe.db.set_value("Healthcare Service Unit", inpatient_occupancy.service_unit, "status", "Vacant")
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
