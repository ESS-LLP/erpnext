# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS LLP and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr
from erpnext.healthcare.utils import manage_healthcare_doc_cancel

class PatientEncounter(Document):
	def on_update(self):
		if self.appointment and self.docstatus == 0:
			frappe.db.set_value("Patient Appointment", self.appointment, "status", "In Progress")
		update_encounter_to_medical_record(self)

	def after_insert(self):
		insert_encounter_to_medical_record(self)

	def on_cancel(self):
		manage_healthcare_doc_cancel(self)
		if(self.appointment):
			frappe.db.set_value("Patient Appointment", self.appointment, "status", "Open")
		delete_medical_record(self)

	def on_submit(self):
		frappe.db.set_value("Patient Appointment", self.appointment, "status", "Closed")

	def before_cancel(self):
		self.validate_orders()

	# Call before delete
	def on_trash(self):
		self.validate_orders()

	def validate_orders(self):
		if self.lab_test_prescription:
			can_not_delete = False
			for lab_rx in self.lab_test_prescription:
				if lab_rx.invoiced:
					can_not_delete = True
					msg = "Invoiced lab test prescription(s)"
				elif lab_rx.lab_test_created:
					can_not_delete = True
					msg = "Lab Test created from procedure prescription"
			if can_not_delete:
				frappe.throw(_("Not permitted. "+msg))
		if self.procedure_prescription:
			can_not_delete = False
			for procedure_rx in self.procedure_prescription:
				if procedure_rx.invoiced:
					can_not_delete = True
					msg = "Invoiced procedure prescription(s)"
				elif procedure_rx.procedure_created:
					can_not_delete = True
					msg = "Procedure created from procedure prescription"
				elif procedure_rx.appointment_booked:
					can_not_delete = True
					msg = "Appointment booked for procedure from procedure prescription"
			if can_not_delete:
				frappe.throw(_("Not permitted. "+msg))

def insert_encounter_to_medical_record(doc):
	subject = set_subject_field(doc)
	medical_record = frappe.new_doc("Patient Medical Record")
	medical_record.patient = doc.patient
	medical_record.subject = subject
	medical_record.status = "Open"
	medical_record.communication_date = doc.encounter_date
	medical_record.reference_doctype = "Patient Encounter"
	medical_record.reference_name = doc.name
	medical_record.reference_owner = doc.owner
	medical_record.save(ignore_permissions=True)

def update_encounter_to_medical_record(encounter):
	medical_record_id = frappe.db.sql("select name from `tabPatient Medical Record` where reference_name=%s", (encounter.name))
	if medical_record_id and medical_record_id[0][0]:
		subject = set_subject_field(encounter)
		frappe.db.set_value("Patient Medical Record", medical_record_id[0][0], "subject", subject)
	else:
		insert_encounter_to_medical_record(encounter)

def delete_medical_record(encounter):
	frappe.db.sql("""delete from `tabPatient Medical Record` where reference_name = %s""", (encounter.name))

def set_subject_field(encounter):
	subject = encounter.practitioner+"<br/>"
	if(encounter.symptoms):
		subject += "Symptoms: "+ cstr(encounter.symptoms)+".<br/>"
	else:
		subject += "No Symptoms <br/>"
	if(encounter.diagnosis):
		subject += "Diagnosis: "+ cstr(encounter.diagnosis)+".<br/>"
	else:
		subject += "No Diagnosis <br/>"
	if(encounter.drug_prescription):
		subject +="\nDrug(s) Prescribed. "
	if(encounter.lab_test_prescription):
		subject += "\nTest(s) Prescribed."
	if(encounter.procedure_prescription):
		subject += "\nProcedure(s) Prescribed."

	return subject
