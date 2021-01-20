# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, getdate, flt
from erpnext.healthcare.utils import sales_item_details_for_healthcare_doc

class EmergencyPatientRecord(Document):
	def before_insert(self):
		if not self.patient:
			create_patient(self)

	def validate(self):
		if self.patient and self.patient_name and self.existing_patient == 0:
			patient_doc = frappe.get_doc('Patient', self.patient)
			if patient_doc.first_name == 'Emergency Patient':
				patient_doc.first_name = self.patient_name
				patient_doc.save(ignore_permissions = True)
				self.existing_patient = 1
				frappe.db.set_value("Customer", self.patient, "customer_name", self.patient_name)

	def schedule_inpatient(doc, service_unit, check_in, expected_discharge=None):
		create_inpatient(doc, service_unit, check_in, expected_discharge)

def create_patient(self):
	patient = frappe.new_doc('Patient')
	patient.first_name = self.patient_name if self.patient_name else 'Emergency Patient'
	patient.sex = self.gender
	patient.blood_group = self.blood_group if self.blood_group else ''
	patient.save(ignore_permissions = True)
	self.patient = patient.name
	frappe.msgprint(_('Patient {0} is created.').format(patient.name), alert=True)

@frappe.whitelist()
def schedule_inpatient(args):
	admission_order = json.loads(args) # admission order via Encounter
	if not admission_order or not admission_order['patient'] or not admission_order['admission_encounter']:
		frappe.throw(_('Missing required details, did not create Inpatient Record'))

	inpatient_record = frappe.new_doc('Inpatient Record')

	for key in admission_order:
		inpatient_record.set(key, admission_order[key])

	# Patient details
	patient = frappe.get_doc('Patient', admission_order['patient'])
	inpatient_record.patient = patient.name
	inpatient_record.patient_name = patient.patient_name
	inpatient_record.gender = patient.sex
	inpatient_record.blood_group = patient.blood_group
	inpatient_record.dob = patient.dob
	inpatient_record.mobile = patient.mobile
	inpatient_record.email = patient.email
	inpatient_record.phone = patient.phone
	inpatient_record.scheduled_date = today()
	inpatient_record.status = 'Admission Scheduled'
	inpatient_record.save(ignore_permissions = True)
	frappe.msgprint(_('Inpatient Record {0} is created.').format(inpatient_record.name), alert=True)

@frappe.whitelist()
def create_invoice(emergency_id):
	emergency_doc = frappe.get_doc("Emergency Patient Record", emergency_id)
	sales_invoice = frappe.new_doc("Sales Invoice")
	sales_invoice.patient = emergency_doc.patient
	sales_invoice.patient_name = emergency_doc.patient_name
	sales_invoice.customer = frappe.get_value("Patient", emergency_doc.patient, "customer")
	sales_invoice.due_date = getdate()
	sales_invoice.inpatient_record = emergency_doc.inpatient_record
	item_line = sales_invoice.append("items")
	item_code = frappe.db.get_value("Appointment Type", emergency_doc.appointment_type, "out_patient_consulting_charge_item")
	cost_center = False
	if emergency_doc.service_unit:
		cost_center = frappe.db.get_value("Healthcare Service Unit", emergency_doc.service_unit, "cost_center")
	if item_code:
		item_line.item_code = item_code
		item_details = sales_item_details_for_healthcare_doc(item_line.item_code, emergency_doc)
		item_line.item_name = item_details.item_name
		item_line.description = frappe.db.get_value("Item", item_line.item_code, "description")
		item_line.rate = item_details.price_list_rate
	item_line.cost_center = cost_center if cost_center else ''
	item_line.qty = 1
	item_line.rate  = float(item_line.rate)
	item_line.reference_dt = "Patient Appointment"
	item_line.reference_dn = emergency_doc.name
	sales_invoice.set_missing_values(for_validate = True)
	return sales_invoice


@frappe.whitelist()
def create_delivery_note(emergency_patient_record, items):
	delivery_note = frappe.new_doc('Delivery Note')
	doc = frappe.get_doc('Emergency Patient Record', emergency_patient_record)
	delivery_note.company = doc.company
	delivery_note.patient = doc.patient
	delivery_note.patient_name = frappe.db.get_value('Patient', doc.patient, 'patient_name')
	delivery_note.customer = frappe.db.get_value('Patient', doc.patient, 'customer')
	delivery_note.emergency_patient_record = emergency_patient_record
	source_service_unit = False
	items = json.loads(items)
	for item_line in items:
		item_line = frappe._dict(item_line)
		source_service_unit = item_line.service_unit
		cost_center = frappe.db.get_value('Healthcare Service Unit', item_line.service_unit, 'cost_center')
		delivery_note.set_warehouse = item_line.warehouse
		set_delivery_note_item(item_line.item, item_line.qty, item_line.warehouse, cost_center, doc, delivery_note, item_line.uom)
	delivery_note.source_service_unit = source_service_unit if source_service_unit else ''
	delivery_note.set_cost_center = frappe.db.get_value('Healthcare Service Unit', source_service_unit, 'cost_center')
	delivery_note.save(ignore_permissions = True)
	delivery_note.submit()

def set_delivery_note_item(item, qty, s_wh, cost_center, doc, delivery_note, uom=False):
	child = delivery_note.append('items')
	item_details = sales_item_details_for_healthcare_doc(item, doc)
	child.item_code = item
	child.item_name = item_details.item_name
	child.uom = uom if uom else item_details.uom
	child.stock_uom = item_details.stock_uom
	child.qty = flt(qty)
	child.warehouse = s_wh
	if not cost_center:
		cost_center = frappe.get_cached_value('Company',  doc.company,  'cost_center')
	child.cost_center = cost_center if cost_center else ''
	child.expense_account = item_details.expense_account
	child.description = frappe.db.get_value('Item', item, 'description')
	child.rate = item_details.price_list_rate
	child.price_list_rate = item_details.price_list_rate
	child.amount = item_details.price_list_rate * child.qty
