# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from erpnext.healthcare.utils import manage_healthcare_doc_cancel
from erpnext.healthcare.doctype.patient_appointment.patient_appointment import update_status
from frappe.utils import cstr

class RadiologyExamination(Document):
	def after_insert(self):
		if self.radiology_procedure_prescription:
			frappe.db.set_value("Radiology Procedure Prescription", self.radiology_procedure_prescription, "radiology_examination_created", True)
		if self.appointment and self.docstatus==0:
			update_status(self.appointment, "In Progress")

	def on_cancel(self):
		manage_healthcare_doc_cancel(self)
		if self.appointment:
			frappe.get_doc("Patient Appointment", self.appointment).save(ignore_permissions=True)

	def on_submit(self):
		insert_to_medical_record(self)
		if self.appointment:
			update_status(self.appointment, "Closed")

	def validate(self):
		ref_company = False
		if self.inpatient_record:
			ref_company = frappe.db.get_value("Inpatient Record", self.inpatient_record, "company")
		elif self.appointment:
			ref_company = frappe.db.get_value("Patient Appointment", self.appointment, "company")
		elif self.service_unit:
			ref_company = frappe.db.get_value("Healthcare Service Unit", self.service_unit, "company")
		if ref_company:
			self.company = ref_company

@frappe.whitelist()
def get_radiology_procedure_prescribed(patient, encounter_practitioner=False):
	query = """
		select
			cp.name, cp.radiology_procedure_name, cp.parent, cp.invoiced, ct.encounter_date, ct.source, ct.referring_practitioner,
			ct.practitioner, ct.insurance, cp.radiology_test_comment
		from
			`tabPatient Encounter` ct, `tabRadiology Procedure Prescription` cp
		where
			ct.patient='{0}' and cp.parent=ct.name and cp.radiology_examination_created=0 and cp.appointment_booked=0
	"""
	if encounter_practitioner:
		query +=""" and ct.practitioner=%(encounter_practitioner)s"""

	query +="""
		order by
			ct.creation desc"""

	return frappe.db.sql(query.format(patient),{
		"encounter_practitioner": encounter_practitioner
	})

@frappe.whitelist()
def create_radiology_examination(appointment):
	appointment = frappe.get_doc("Patient Appointment",appointment)
	radiology_examination = frappe.new_doc("Radiology Examination")
	radiology_examination.appointment = appointment.name
	radiology_examination.patient = appointment.patient
	radiology_examination.radiology_procedure = appointment.radiology_procedure
	radiology_examination.radiology_procedure_prescription = appointment.radiology_procedure_prescription
	radiology_examination.practitioner = appointment.practitioner
	radiology_examination.invoiced = appointment.invoiced
	radiology_examination.medical_department = appointment.department
	radiology_examination.start_date = appointment.appointment_date
	radiology_examination.start_time = appointment.appointment_time
	radiology_examination.notes = appointment.notes
	radiology_examination.service_unit = appointment.service_unit
	radiology_examination.company = appointment.company
	radiology_examination.modality_type = appointment.modality_type
	radiology_examination.modality = appointment.modality
	if appointment.insurance:
		radiology_examination.insurance=appointment.insurance
	radiology_examination.source=appointment.source
	if appointment.referring_practitioner:
		radiology_examination.referring_practitioner=appointment.referring_practitioner
	if appointment.insurance_approval_number:
		radiology_examination.insurance_approval_number=appointment.insurance_approval_number
	return radiology_examination.as_dict()

def insert_to_medical_record(doc):
	subject = cstr(doc.radiology_procedure)
	if doc.practitioner:
		subject += " "+doc.practitioner
	if subject and doc.notes:
		subject += "<br/>"+doc.notes

	medical_record = frappe.new_doc("Patient Medical Record")
	medical_record.patient = doc.patient
	medical_record.subject = subject
	medical_record.status = "Open"
	medical_record.communication_date = doc.start_date
	medical_record.reference_doctype = "Radiology Examination"
	medical_record.reference_name = doc.name
	medical_record.reference_owner = doc.owner
	medical_record.save(ignore_permissions=True)
