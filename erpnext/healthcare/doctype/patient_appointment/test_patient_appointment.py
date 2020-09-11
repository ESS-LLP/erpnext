# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS LLP and Contributors
# See license.txt
from __future__ import unicode_literals
import unittest
import frappe
from frappe import _
from erpnext.healthcare.doctype.patient_appointment.patient_appointment import update_status, make_encounter
from frappe.utils import nowdate, add_days
from frappe.utils.make_random import get_random

class TestPatientAppointment(unittest.TestCase):
	def setUp(self):
		frappe.db.sql("""delete from `tabPatient Appointment`""")
		frappe.db.sql("""delete from `tabFee Validity`""")
		frappe.db.sql("""delete from `tabPatient Encounter`""")
		frappe.db.sql("""delete from `tabHealthcare Service Unit Type`""")
		frappe.db.sql("""delete from `tabHealthcare Service Unit`""")

	def test_status(self):
		patient, medical_department, practitioner = create_healthcare_docs()
		frappe.db.set_value('Healthcare Settings', None, 'automate_appointment_invoicing', 0)
		appointment = create_appointment(patient, practitioner, nowdate())
		self.assertEquals(appointment.status, 'Open')
		appointment = create_appointment(patient, practitioner, add_days(nowdate(), 2))
		self.assertEquals(appointment.status, 'Scheduled')
		create_encounter(appointment)
		self.assertEquals(frappe.db.get_value('Patient Appointment', appointment.name, 'status'), 'Closed')

	def test_start_encounter(self):
		patient, medical_department, practitioner = create_healthcare_docs()
		frappe.db.set_value('Healthcare Settings', None, 'automate_appointment_invoicing', 1)
		appointment = create_appointment(patient, practitioner, add_days(nowdate(), 4), invoice = 1)
		self.assertEqual(frappe.db.get_value('Patient Appointment', appointment.name, 'invoiced'), 1)
		encounter = make_encounter(appointment.name)
		self.assertTrue(encounter)
		self.assertEqual(encounter.company, appointment.company)
		self.assertEqual(encounter.practitioner, appointment.practitioner)
		self.assertEqual(encounter.patient, appointment.patient)
		# invoiced flag mapped from appointment
		self.assertEqual(encounter.invoiced, frappe.db.get_value('Patient Appointment', appointment.name, 'invoiced'))

	def test_invoicing(self):
		patient, medical_department, practitioner = create_healthcare_docs()
		frappe.db.set_value('Healthcare Settings', None, 'enable_free_follow_ups', 0)
		frappe.db.set_value('Healthcare Settings', None, 'automate_appointment_invoicing', 0)
		appointment = create_appointment(patient, practitioner, nowdate())
		self.assertEqual(frappe.db.get_value('Patient Appointment', appointment.name, 'invoiced'), 0)

		frappe.db.set_value('Healthcare Settings', None, 'automate_appointment_invoicing', 1)
		appointment = create_appointment(patient, practitioner, add_days(nowdate(), 2), invoice=1)
		self.assertEqual(frappe.db.get_value('Patient Appointment', appointment.name, 'invoiced'), 1)
		sales_invoice_name = frappe.db.get_value('Sales Invoice Item', {'reference_dn': appointment.name}, 'parent')
		self.assertTrue(sales_invoice_name)
		self.assertEqual(frappe.db.get_value('Sales Invoice', sales_invoice_name, 'company'), appointment.company)
		self.assertEqual(frappe.db.get_value('Sales Invoice', sales_invoice_name, 'patient'), appointment.patient)
		self.assertEqual(frappe.db.get_value('Sales Invoice', sales_invoice_name, 'paid_amount'), appointment.paid_amount)

	def test_appointment_cancel(self):
		patient, medical_department, practitioner = create_healthcare_docs()
		frappe.db.set_value('Healthcare Settings', None, 'enable_free_follow_ups', 1)
		appointment = create_appointment(patient, practitioner, nowdate())
		fee_validity = frappe.db.get_value('Fee Validity Reference', {'appointment': appointment.name}, 'parent')
		# fee validity created
		self.assertTrue(fee_validity)

		visited = frappe.db.get_value('Fee Validity', fee_validity, 'visited')
		update_status(appointment.name, 'Cancelled')
		# check fee validity updated
		self.assertEqual(frappe.db.get_value('Fee Validity', fee_validity, 'visited'), visited - 1)

		frappe.db.set_value('Healthcare Settings', None, 'enable_free_follow_ups', 0)
		frappe.db.set_value('Healthcare Settings', None, 'automate_appointment_invoicing', 1)
		appointment = create_appointment(patient, practitioner, nowdate(), invoice=1)
		update_status(appointment.name, 'Cancelled')
		# check invoice cancelled
		sales_invoice_name = frappe.db.get_value('Sales Invoice Item', {'reference_dn': appointment.name}, 'parent')
		self.assertEqual(frappe.db.get_value('Sales Invoice', sales_invoice_name, 'status'), 'Cancelled')

	def test_appointment_overlap(self):
		patient, medical_department, practitioner = create_healthcare_docs()
		service_unit_type = create_service_unit_type()
		overlap_service_unit_type = create_overlap_service_unit_type()
		service_unit = create_service_unit(service_unit_type)
		overlap_service_unit = create_overlap_service_unit(overlap_service_unit_type)
		from erpnext.healthcare.doctype.patient_appointment.patient_appointment import Maximumcapacityerror, Overlappingerror
		for y in range(2, 5):
			try:
				patient_2 = create_patient_n(y)
				appointment = create_appointments(patient_2, practitioner, nowdate(), overlap_service_unit)
			except:
				self.assertRaises(Maximumcapacityerror)
		for x in range(0, 1):
			try:
				patient_1 = create_patient_n(x)
				appointment = create_appointments(patient_1, practitioner, nowdate(), service_unit)
			except:
				self.assertRaises(Overlappingerror)

def create_healthcare_docs():
	patient = create_patient()
	practitioner = frappe.db.exists('Healthcare Practitioner', '_Test Healthcare Practitioner')
	medical_department = frappe.db.exists('Medical Department', '_Test Medical Department')


	if not medical_department:
		medical_department = frappe.new_doc('Medical Department')
		medical_department.department = '_Test Medical Department'
		medical_department.save(ignore_permissions=True)
		medical_department = medical_department.name

	if not practitioner:
		practitioner = frappe.new_doc('Healthcare Practitioner')
		practitioner.first_name = '_Test Healthcare Practitioner'
		practitioner.gender = 'Female'
		practitioner.department = medical_department
		practitioner.op_consulting_charge = 500
		practitioner.inpatient_visit_charge = 500
		practitioner.save(ignore_permissions=True)
		practitioner = practitioner.name

	return patient, medical_department, practitioner

def create_patient():
	patient = frappe.db.exists('Patient', '_Test Patient')
	if not patient:
		patient = frappe.new_doc('Patient')
		patient.first_name = '_Test Patient'
		patient.sex = 'Female'
		patient.save(ignore_permissions=True)
		patient = patient.name
	return patient

def create_encounter(appointment):
	if appointment:
		encounter = frappe.new_doc('Patient Encounter')
		encounter.appointment = appointment.name
		encounter.patient = appointment.patient
		encounter.practitioner = appointment.practitioner
		encounter.encounter_date = appointment.appointment_date
		encounter.encounter_time = appointment.appointment_time
		encounter.company = appointment.company
		encounter.save()
		encounter.submit()
		return encounter

def create_appointment(patient, practitioner, appointment_date, invoice=0, procedure_template=0):
	item = create_healthcare_service_items()
	frappe.db.set_value('Healthcare Settings', None, 'inpatient_visit_charge_item', item)
	frappe.db.set_value('Healthcare Settings', None, 'op_consulting_charge_item', item)
	appointment = frappe.new_doc('Patient Appointment')
	appointment.patient = patient
	appointment.practitioner = practitioner
	appointment.department = '_Test Medical Department'
	appointment.appointment_date = appointment_date
	appointment.company = '_Test Company'
	appointment.duration = 15
	if invoice:
		appointment.mode_of_payment = 'Cash'
		appointment.paid_amount = 500
	if procedure_template:
		appointment.procedure_template = create_clinical_procedure_template().get('name')
	appointment.save(ignore_permissions=True)
	return appointment

def create_healthcare_service_items():
	if frappe.db.exists('Item', 'HLC-SI-001'):
		return 'HLC-SI-001'
	item = frappe.new_doc('Item')
	item.item_code = 'HLC-SI-001'
	item.item_name = 'Consulting Charges'
	item.item_group = 'Services'
	item.is_stock_item = 0
	item.save()
	return item.name

def create_clinical_procedure_template():
	if frappe.db.exists('Clinical Procedure Template', 'Knee Surgery and Rehab'):
		return frappe.get_doc('Clinical Procedure Template', 'Knee Surgery and Rehab')
	template = frappe.new_doc('Clinical Procedure Template')
	template.template = 'Knee Surgery and Rehab'
	template.item_code = 'Knee Surgery and Rehab'
	template.item_group = 'Services'
	template.is_billable = 1
	template.description = 'Knee Surgery and Rehab'
	template.rate = 50000
	template.save()
	return template

def create_service_unit_type():
	service_unit_type = frappe.db.exists('Healthcare Service Unit Type', '_Test service_unit_type')
	if not service_unit_type:
		service_unit_type = frappe.new_doc('Healthcare Service Unit Type')
		service_unit_type.service_unit_type = '_Test service_unit_type'
		service_unit_type.allow_appointments = 1
		service_unit_type.save(ignore_permissions=True)
		service_unit_type = service_unit_type.name
		return service_unit_type

def create_overlap_service_unit_type():
	overlap_service_unit_type = frappe.db.exists('Healthcare Service Unit Type', '_Test overlap_service_unit_type')
	if not overlap_service_unit_type:
		overlap_service_unit_type = frappe.new_doc('Healthcare Service Unit Type')
		overlap_service_unit_type.service_unit_type = '_Test overlap_service_unit_type'
		overlap_service_unit_type.allow_appointments = 1
		overlap_service_unit_type.overlap_appointments = 1
		overlap_service_unit_type.save(ignore_permissions=True)
		overlap_service_unit_type = overlap_service_unit_type.name
	return overlap_service_unit_type


def create_service_unit(service_unit_type):
	service_unit = frappe.db.exists('Healthcare Service Unit', '_Test service_unit')
	if not service_unit:
		service_unit = frappe.new_doc('Healthcare Service Unit')
		service_unit.healthcare_service_unit_name= '_Test service_unit'
		service_unit.service_unit_type = service_unit_type
		service_unit.save(ignore_permissions=True)
		service_unit = service_unit.name
	return service_unit

def create_overlap_service_unit(overlap_service_unit_type):
	overlap_service_unit = frappe.db.exists('Healthcare Service Unit', '_Test overlap_service_unit')
	if not overlap_service_unit:
		overlap_service_unit = frappe.new_doc('Healthcare Service Unit')
		overlap_service_unit.healthcare_service_unit_name= '_Test overlap_service_unit'
		overlap_service_unit.total_service_unit_capacity = 3
		overlap_service_unit.service_unit_type = overlap_service_unit_type
		overlap_service_unit.save(ignore_permissions=True)
		overlap_service_unit = overlap_service_unit.name
	return overlap_service_unit

def create_patient_n(x):
	x = str(x)
	patient = frappe.db.exists('Patient', '_Test Patient'+ x)
	if not patient:
		patient = frappe.new_doc('Patient')
		patient.first_name = '_Test Patient'+ x
		patient.sex = 'Female'
		patient.save(ignore_permissions=True)
		patient = patient.name
	return patient

def create_appointments(patient, practitioner, appointment_date, service_unit):
	appointment = frappe.new_doc('Patient Appointment')
	appointment.patient = patient
	appointment.practitioner = practitioner
	appointment.department = '_Test Medical Department'
	appointment.appointment_date = appointment_date
	appointment.company = '_Test Company'
	appointment.service_unit = service_unit
	appointment.duration = 30
	appointment.save(ignore_permissions=True)
	return appointment
