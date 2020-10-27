# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from erpnext.healthcare.utils import manage_healthcare_doc_cancel
from frappe.utils import cstr


class RadiologyExamination(Document):
	def after_insert(self):
		if self.radiology_procedure_prescription:
			frappe.db.set_value('Radiology Procedure Prescription',
			                    self.radiology_procedure_prescription, 'radiology_examination_created', True)
			frappe.db.set_value('Radiology Procedure Prescription',
			                    self.radiology_procedure_prescription, 'radiology_examination', self.name)

	def on_cancel(self):
		manage_healthcare_doc_cancel(self)

	def on_submit(self):
		insert_to_medical_record(self)
		make_insurance_claim(self)

	def validate(self):
		set_title_field(self)
		ref_company = False
		if self.inpatient_record:
			ref_company = frappe.db.get_value(
				'Inpatient Record', self.inpatient_record, 'company')
		elif self.service_unit:
			ref_company = frappe.db.get_value(
				'Healthcare Service Unit', self.service_unit, 'company')
		if ref_company:
			self.company = ref_company

def set_title_field(self):
	self.title = _('{0} - {1}').format(self.patient, self.radiology_examination_template)[:100]

def insert_to_medical_record(doc):
    subject = cstr(doc.radiology_examination_template)
    if doc.practitioner:
        subject += ' '+doc.practitioner
    if subject and doc.notes:
        subject += '<br/>'+doc.notes

    medical_record = frappe.new_doc('Patient Medical Record')
    medical_record.patient = doc.patient
    medical_record.subject = subject
    medical_record.status = 'Open'
    medical_record.communication_date = doc.start_date
    medical_record.reference_doctype = 'Radiology Examination'
    medical_record.reference_name = doc.name
    medical_record.reference_owner = doc.owner
    medical_record.save(ignore_permissions=True)

@frappe.whitelist()
def get_radiology_procedure_prescribed(patient, encounter_practitioner=False):
	query = """
		SELECT
			cp.name, cp.radiology_examination_template, cp.parent, ct.invoiced, ct.encounter_date, ct.source, ct.referring_practitioner,
			ct.practitioner, cp.radiology_test_comment
		FROM
			`tabPatient Encounter` ct, `tabRadiology Procedure Prescription` cp
		WHERE
			ct.patient='{0}' and cp.parent=ct.name and cp.radiology_examination_created=0 and cp.appointment_booked=0
	"""
	if encounter_practitioner:
		query +=""" and ct.practitioner=%(encounter_practitioner)s"""

	query +="""
		ORDER BY
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
	radiology_examination.radiology_examination_template = appointment.radiology_examination_template
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
	radiology_examination.source=appointment.source
	if appointment.referring_practitioner:
		radiology_examination.referring_practitioner=appointment.referring_practitioner
	return radiology_examination.as_dict()

def make_insurance_claim(doc):
	if doc.insurance_subscription:
		from erpnext.healthcare.utils import create_insurance_claim
		billing_item, = frappe.get_cached_value('Radiology Examination Template', doc.radiology_examination_template, ['item'])
		insurance_claim, claim_status = create_insurance_claim(doc, 'Radiology Examination Template', doc.radiology_examination_template, 1, billing_item)
		if insurance_claim:
			frappe.set_value(doc.doctype, doc.name ,'insurance_claim', insurance_claim)
			frappe.set_value(doc.doctype, doc.name ,'claim_status', claim_status)
			doc.reload()
