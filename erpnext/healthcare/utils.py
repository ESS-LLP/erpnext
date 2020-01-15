# -*- coding: utf-8 -*-
# Copyright (c) 2018, earthians and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
import datetime
from frappe import _
import math
from frappe.utils import time_diff_in_hours, rounded, getdate, add_days, nowdate, nowtime
from erpnext.healthcare.doctype.healthcare_settings.healthcare_settings import get_income_account
from erpnext.healthcare.doctype.fee_validity.fee_validity import create_fee_validity, update_fee_validity
from erpnext.healthcare.doctype.lab_test.lab_test import create_multiple
from erpnext.stock.get_item_details import get_item_details

@frappe.whitelist()
def get_healthcare_services_to_invoice(patient, insurance=None):
	patient = frappe.get_doc("Patient", patient)
	if patient:
		include_in_insurance = True if insurance else False
		filters = {'patient': patient.name, 'invoiced': False, 'docstatus': 1, 'insurance': insurance if insurance else ''}
		if patient.customer:
			item_to_invoice = []
			patient_appointments = frappe.get_list("Patient Appointment", {'patient': patient.name, 'invoiced': False, 'insurance': insurance if insurance else ''}, order_by="appointment_date")
			if patient_appointments:
				fee_validity_details = []
				valid_days = frappe.db.get_value("Healthcare Settings", None, "valid_days")
				max_visit = frappe.db.get_value("Healthcare Settings", None, "max_visit")
				for patient_appointment in patient_appointments:
					cost_center = False
					patient_appointment_obj = frappe.get_doc("Patient Appointment", patient_appointment['name'])
					if patient_appointment_obj.service_unit:
						cost_center = frappe.db.get_value("Healthcare Service Unit", patient_appointment_obj.service_unit, "cost_center")
					if patient_appointment_obj.procedure_template:
						if frappe.db.get_value("Clinical Procedure Template", patient_appointment_obj.procedure_template, "is_billable") == 1:
							app_service_item = frappe.db.get_value("Clinical Procedure Template", patient_appointment_obj.procedure_template, "item")
							service_item_name=frappe.db.get_value("Item", app_service_item, "item_name" )
							insurance_details = False
							if include_in_insurance:
								insurance_details = get_insurance_details(patient_appointment_obj.insurance, app_service_item, patient)
							if include_in_insurance and insurance_details:
								invoice_item = {'reference_dt': 'Patient Appointment', 'reference_dn': patient_appointment_obj.name,
									'item_code': app_service_item, 'cost_center': cost_center if cost_center else '', 'item_name':service_item_name,
									'discount_percentage': insurance_details.discount, 'insurance_claim_coverage': insurance_details.coverage, 'insurance_approval_number': patient_appointment_obj.insurance_approval_number if patient_appointment_obj.insurance_approval_number else ''}
								if insurance_details.rate:
									invoice_item['rate'] = insurance_details.rate,
								item_to_invoice.append(invoice_item)
							else:
								item_to_invoice.append({'reference_dt': 'Patient Appointment', 'reference_dn': patient_appointment_obj.name, 'item_name':service_item_name,
									'item_code': app_service_item, 'cost_center': cost_center if cost_center else ''})
					elif patient_appointment_obj.radiology_procedure:
						if frappe.db.get_value("Radiology Procedure", patient_appointment_obj.radiology_procedure, "is_billable") == 1:
							app_radiology_service_item = frappe.db.get_value("Radiology Procedure", patient_appointment_obj.radiology_procedure, "item")
							service_item_name=frappe.db.get_value("Item", app_radiology_service_item, "item_name" )
							insurance_details = False
							if include_in_insurance:
								insurance_details = get_insurance_details(patient_appointment_obj.insurance, app_radiology_service_item, patient)
							if include_in_insurance and insurance_details:
								invoice_item={'reference_dt': 'Patient Appointment', 'reference_dn': patient_appointment_obj.name,
									'item_code': app_radiology_service_item, 'cost_center': cost_center if cost_center else '', 'item_name':service_item_name,
									'discount_percentage': insurance_details.discount, 'insurance_claim_coverage': insurance_details.coverage, 'insurance_approval_number': patient_appointment_obj.insurance_approval_number if patient_appointment_obj.insurance_approval_number else ''}
								if insurance_details.rate:
									invoice_item['rate'] = insurance_details.rate,
								item_to_invoice.append(invoice_item)
							else:
								item_to_invoice.append({'reference_dt': 'Patient Appointment', 'reference_dn': patient_appointment_obj.name, 'item_name':service_item_name,
								'item_code': patient_appointment_obj.radiology_procedure, 'cost_center': cost_center if cost_center else ''})
					else:
						practitioner_exist_in_list = False
						skip_invoice = False
						if fee_validity_details:
							for validity in fee_validity_details:
								if validity['practitioner'] == patient_appointment_obj.practitioner:
									practitioner_exist_in_list = True
									if validity['valid_till'] >= patient_appointment_obj.appointment_date:
										validity['visits'] = validity['visits']+1
										if int(max_visit) > validity['visits']:
											skip_invoice = True
									if not skip_invoice:
										validity['visits'] = 1
										validity['valid_till'] = patient_appointment_obj.appointment_date + datetime.timedelta(days=int(valid_days))
						if not practitioner_exist_in_list and not include_in_insurance:
							valid_till = patient_appointment_obj.appointment_date + datetime.timedelta(days=int(valid_days))
							visits = 0
							validity_exist = validity_exists(patient_appointment_obj.practitioner, patient_appointment_obj.patient)
							if validity_exist:
								fee_validity = frappe.get_doc("Fee Validity", validity_exist[0][0])
								valid_till = fee_validity.valid_till
								visits = fee_validity.visited
							fee_validity_details.append({'practitioner': patient_appointment_obj.practitioner,
							'valid_till': valid_till, 'visits': visits})

						service_item, practitioner_charge = service_item_and_practitioner_charge(patient_appointment_obj)
						service_item_name= frappe.db.get_value("Item", service_item, "item_name")
						if not practitioner_charge: # skip billing if charge not configured
							skip_invoice = True

						if not skip_invoice:
							income_account = None
							if patient_appointment_obj.practitioner:
								income_account = get_income_account(patient_appointment_obj.practitioner, patient_appointment_obj.company)
							insurance_details = False
							if include_in_insurance:
								insurance_details = get_insurance_details(patient_appointment_obj.insurance, service_item, patient)
							if include_in_insurance and insurance_details:
								if insurance_details.rate:
									practitioner_charge = insurance_details.rate
								item_to_invoice.append({'reference_dt': 'Patient Appointment', 'reference_dn': patient_appointment_obj.name, 'item_name':service_item_name,
									'item_code': service_item, 'cost_center': cost_center if cost_center else '', 'rate': practitioner_charge, 'income_account': income_account,
									'discount_percentage': insurance_details.discount, 'insurance_claim_coverage': insurance_details.coverage, 'insurance_approval_number': patient_appointment_obj.insurance_approval_number if patient_appointment_obj.insurance_approval_number else ''})
							else:
								item_to_invoice.append({'reference_dt': 'Patient Appointment', 'reference_dn': patient_appointment_obj.name, 'item_name':service_item_name,
									'item_code': service_item, 'cost_center': cost_center if cost_center else '', 'rate': practitioner_charge, 'income_account': income_account})
			encounters = frappe.get_list("Patient Encounter", filters)
			if encounters:
				for encounter in encounters:
					cost_center = False
					encounter_obj = frappe.get_doc("Patient Encounter", encounter['name'])
					if encounter_obj.service_unit:
						cost_center = frappe.db.get_value("Healthcare Service Unit", encounter_obj.service_unit, "cost_center")
					if not encounter_obj.appointment:
						practitioner_charge = 0
						income_account = None
						service_item = None
						if encounter_obj.practitioner:
							service_item, practitioner_charge = service_item_and_practitioner_charge(encounter_obj)
							service_item_name= frappe.db.get_value("Item", service_item, "item_name")
							if not practitioner_charge: # skip billing if charge not configured
								continue
							income_account = get_income_account(encounter_obj.practitioner, encounter_obj.company)
						insurance_details = False
						if include_in_insurance :
							insurance_details = get_insurance_details(encounter_obj.insurance, service_item, patient)
						if include_in_insurance and insurance_details:
							if insurance_details.rate:
								practitioner_charge = insurance_details.rate
							item_to_invoice.append({'reference_dt': 'Patient Encounter', 'reference_dn': encounter_obj.name, 'item_name':service_item_name,
							'item_code': service_item, 'rate': practitioner_charge, 'cost_center': cost_center if cost_center else '', 'discount_percentage': insurance_details.discount,
							'income_account': income_account, 'insurance_claim_coverage': insurance_details.coverage, 'insurance_approval_number': encounter_obj.insurance_approval_number if encounter_obj.insurance_approval_number else ''})
						else:
							item_to_invoice.append({'reference_dt': 'Patient Encounter', 'reference_dn': encounter_obj.name, 'item_name':service_item_name,
							'item_code': service_item, 'rate': practitioner_charge, 'cost_center': cost_center if cost_center else '',
							'income_account': income_account})
			lab_tests = frappe.get_list("Lab Test", filters)
			if lab_tests:
				for lab_test in lab_tests:
					cost_center = False
					lab_test_obj = frappe.get_doc("Lab Test", lab_test['name'])
					if lab_test_obj.service_unit:
						cost_center = frappe.db.get_value("Healthcare Service Unit", lab_test_obj.service_unit, "cost_center")
					if frappe.db.get_value("Lab Test Template", lab_test_obj.template, "is_billable") == 1:
						service_item_name=frappe.db.get_value("Item", frappe.db.get_value("Lab Test Template", lab_test_obj.template, "item"), "item_name" )
						insurance_details = False
						if include_in_insurance:
							insurance_details = get_insurance_details(lab_test_obj.insurance, frappe.db.get_value("Lab Test Template", lab_test_obj.template, "item"), patient)
						if include_in_insurance and insurance_details:
							invoice_item={'reference_dt': 'Lab Test', 'reference_dn': lab_test_obj.name, 'item_name':service_item_name,
							'item_code': frappe.db.get_value("Lab Test Template", lab_test_obj.template, "item"), 'cost_center': cost_center if cost_center else '',
							'discount_percentage': insurance_details.discount, 'insurance_claim_coverage': insurance_details.coverage, 'insurance_approval_number': lab_test_obj.insurance_approval_number if lab_test_obj.insurance_approval_number else ''}
							if insurance_details.rate:
								invoice_item['rate'] = insurance_details.rate,
							item_to_invoice.append(invoice_item)
						else:
							item_to_invoice.append({'reference_dt': 'Lab Test', 'reference_dn': lab_test_obj.name, 'item_name':service_item_name,
							'item_code': frappe.db.get_value("Lab Test Template", lab_test_obj.template, "item"), 'cost_center': cost_center if cost_center else ''})

			lab_rxs = frappe.db.sql("""select lp.name,et.name from `tabPatient Encounter` et, `tabLab Prescription` lp
			where et.patient=%s and lp.parent=et.name and lp.lab_test_created=0 and lp.invoiced=0""", (patient.name))
			if lab_rxs:
				for lab_rx in lab_rxs:
					cost_center = False
					rx_obj = frappe.get_doc("Lab Prescription", lab_rx[0])
					if rx_obj.parenttype == "Patient Encounter":
						rx_obj_service_unit = frappe.get_value("Patient Encounter", rx_obj.parent, "service_unit")
						if rx_obj_service_unit:
							cost_center = frappe.db.get_value("Healthcare Service Unit", rx_obj_service_unit, "cost_center")
					encx_obj = frappe.get_doc("Patient Encounter", lab_rx[1])
					if rx_obj.lab_test_code and (frappe.db.get_value("Lab Test Template", rx_obj.lab_test_code, "is_billable") == 1):
						service_item_name=frappe.db.get_value("Item", frappe.db.get_value("Lab Test Template", rx_obj.lab_test_code, "item"), "item_name" )
						insurance_details = False
						if include_in_insurance and encx_obj.insurance:
							insurance_details = get_insurance_details(encx_obj.insurance, frappe.db.get_value("Lab Test Template", rx_obj.lab_test_code, "item"), patient)
						if include_in_insurance and insurance_details:
							invoice_item={'reference_dt': 'Lab Prescription', 'reference_dn': rx_obj.name,
							'item_code': frappe.db.get_value("Lab Test Template", rx_obj.lab_test_code, "item"), 'cost_center': cost_center if cost_center else '', 'item_name':service_item_name,
							'discount_percentage': insurance_details.discount, 'insurance_claim_coverage': insurance_details.coverage, 'insurance_approval_number': encx_obj.insurance_approval_number if encx_obj.insurance_approval_number else ''}
							if insurance_details.rate:
								invoice_item['rate'] = insurance_details.rate,
							item_to_invoice.append(invoice_item)
						elif not include_in_insurance and not encx_obj.insurance:
							item_to_invoice.append({'reference_dt': 'Lab Prescription', 'reference_dn': rx_obj.name, 'item_name':service_item_name,
							'item_code': frappe.db.get_value("Lab Test Template", rx_obj.lab_test_code, "item"), 'cost_center': cost_center if cost_center else ''})
			procedures = frappe.get_list("Clinical Procedure", {'patient': patient.name, 'invoiced': False, 'docstatus': 1, 'status': 'Completed', 'insurance': insurance if insurance else ''})
			if procedures:
				for procedure in procedures:
					cost_center = False
					procedure_obj = frappe.get_doc("Clinical Procedure", procedure['name'])
					if procedure_obj.service_unit:
						cost_center = frappe.db.get_value("Healthcare Service Unit", procedure_obj.service_unit, "cost_center")
					if not procedure_obj.appointment and procedure_obj.procedure_template and (frappe.db.get_value("Clinical Procedure Template", procedure_obj.procedure_template, "is_billable") == 1):
						reduce_from_procedure_rate = 0
						if procedure_obj.consume_stock:
							delivery_note_items = get_procedure_delivery_item(patient.name, procedure_obj.name)
							if delivery_note_items:
								for delivery_note_item in delivery_note_items:
									dn_item = frappe.get_doc("Delivery Note Item", delivery_note_item[0])
									reduce_from_procedure_rate += item_reduce_procedure_rate(dn_item, procedure_obj.items)
						procedure_service_item = frappe.db.get_value("Clinical Procedure Template", procedure_obj.procedure_template, "item")
						service_item_name=frappe.db.get_value("Item",procedure_service_item, "item_name" )
						insurance_details = False
						if include_in_insurance :
							insurance_details = get_insurance_details(procedure_obj.insurance, procedure_service_item, patient)
						if include_in_insurance and insurance_details:
							invoice_item={'reference_dt': 'Clinical Procedure', 'reference_dn': procedure_obj.name, 'item_name':service_item_name,
							'item_code': procedure_service_item, 'cost_center': cost_center if cost_center else '',
							'discount_percentage': insurance_details.discount, 'insurance_claim_coverage': insurance_details.coverage, 'insurance_approval_number': procedure_obj.insurance_approval_number if procedure_obj.insurance_approval_number else ''}
							if insurance_details.rate:
								invoice_item['rate'] = insurance_details.rate-reduce_from_procedure_rate
							else:
								invoice_item['rate'] = float(procedure_obj.standard_selling_rate)-reduce_from_procedure_rate
							item_to_invoice.append(invoice_item)
						else:
							item_to_invoice.append({'reference_dt': 'Clinical Procedure', 'reference_dn': procedure_obj.name, 'cost_center': cost_center if cost_center else '', 'item_name':service_item_name,
								'item_code': procedure_service_item, 'rate': float(procedure_obj.standard_selling_rate)-reduce_from_procedure_rate})

			procedure_rxs = frappe.db.sql("""select pp.name, et.name from `tabPatient Encounter` et,
			`tabProcedure Prescription` pp where et.patient=%s and pp.parent=et.name and
			pp.procedure_created=0 and pp.invoiced=0 and pp.appointment_booked=0""", (patient.name))
			if procedure_rxs:
				for procedure_rx in procedure_rxs:
					cost_center = False
					rx_obj = frappe.get_doc("Procedure Prescription", procedure_rx[0])
					if rx_obj.parenttype == "Patient Encounter":
						rx_obj_service_unit = frappe.get_value("Patient Encounter", rx_obj.parent, "service_unit")
						if rx_obj_service_unit:
							cost_center = frappe.db.get_value("Healthcare Service Unit", rx_obj_service_unit, "cost_center")
					encx_obj = frappe.get_doc("Patient Encounter", procedure_rx[1])
					if frappe.db.get_value("Clinical Procedure Template", rx_obj.procedure, "is_billable") == 1:
						service_item_name=frappe.db.get_value("Item",frappe.db.get_value("Clinical Procedure Template", rx_obj.procedure, "item"), "item_name" )
						insurance_details = False
						if include_in_insurance and encx_obj.insurance:
							insurance_details = get_insurance_details(encx_obj.insurance, frappe.db.get_value("Clinical Procedure Template", rx_obj.procedure, "item"), patient)
						if include_in_insurance and insurance_details:
							invoice_item={'reference_dt': 'Procedure Prescription', 'reference_dn': rx_obj.name, 'item_name':service_item_name,
							 'item_code': frappe.db.get_value("Clinical Procedure Template", rx_obj.procedure, "item"), 'cost_center': cost_center if cost_center else '',
							 'discount_percentage': insurance_details.discount, 'insurance_claim_coverage': insurance_details.coverage, 'insurance_approval_number': encx_obj.insurance_approval_number if encx_obj.insurance_approval_number else ''}
							if insurance_details.rate:
								invoice_item['rate'] = insurance_details.rate,
							item_to_invoice.append(invoice_item)
						elif not include_in_insurance and not encx_obj.insurance:
							item_to_invoice.append({'reference_dt': 'Procedure Prescription', 'reference_dn': rx_obj.name, 'item_name':service_item_name,
							'item_code': frappe.db.get_value("Clinical Procedure Template", rx_obj.procedure, "item"), 'cost_center': cost_center if cost_center else '',})

			r_procedures = frappe.get_list("Radiology Examination", filters)
			if r_procedures:
				for procedure in r_procedures:
					cost_center = False
					procedure_obj = frappe.get_doc("Radiology Examination", procedure['name'])
					if procedure_obj.service_unit:
						cost_center = frappe.db.get_value("Healthcare Service Unit", procedure_obj.service_unit, "cost_center")
					if not procedure_obj.appointment:
						if procedure_obj.radiology_procedure and (frappe.db.get_value("Radiology Procedure", procedure_obj.radiology_procedure, "is_billable") == 1):
							procedure_service_item = frappe.db.get_value("Radiology Procedure", procedure_obj.radiology_procedure, "item")
							service_item_name=frappe.db.get_value("Item", procedure_service_item, "item_name")
							insurance_details = False
							if include_in_insurance:
								insurance_details = get_insurance_details(procedure_obj.insurance, procedure_service_item, patient)
							if include_in_insurance and insurance_details:
								invoice_item={'reference_dt': 'Radiology Examination', 'reference_dn': procedure_obj.name, 'item_name':service_item_name,
								'cost_center': cost_center if cost_center else '', 'item_code': procedure_service_item,
								'discount_percentage': insurance_details.discount, 'insurance_claim_coverage': insurance_details.coverage, 'insurance_approval_number': procedure_obj.insurance_approval_number if procedure_obj.insurance_approval_number else ''}
								if insurance_details.rate:
									invoice_item['rate'] = insurance_details.rate,
								item_to_invoice.append(invoice_item)

							else:
								item_to_invoice.append({'reference_dt': 'Radiology Examination', 'reference_dn': procedure_obj.name, 'item_name':service_item_name,
								'cost_center': cost_center if cost_center else '', 'item_code': procedure_service_item})

			delivery_note_items = get_procedure_delivery_item(patient.name)
			if delivery_note_items:
				for delivery_note_item in delivery_note_items:
					cost_center = False
					reference_type = False
					reference_name = False
					insurance_details = False
					delivery_note = frappe.get_doc("Delivery Note", delivery_note_item[1])
					dn_item = frappe.get_doc("Delivery Note Item", delivery_note_item[0])
					if dn_item.reference_dt == "Clinical Procedure" and dn_item.reference_dn:
						service_unit = frappe.get_value("Clinical Procedure", dn_item.reference_dn, 'service_unit')
						if service_unit:
							cost_center = frappe.db.get_value("Healthcare Service Unit", service_unit, "cost_center")

					if include_in_insurance and delivery_note.insurance:
						insurance_details = get_insurance_details(delivery_note.insurance, dn_item.item_code, patient)
					if include_in_insurance and insurance_details:
						invoice_item = {'reference_dt': "Delivery Note", 'reference_dn': delivery_note_item[1] if delivery_note_item[1] else '',
						'item_code': dn_item.item_code, 'rate': dn_item.rate, 'qty': dn_item.qty, 'item_name':dn_item.item_name,
						'cost_center': cost_center if cost_center else dn_item.cost_center,
						'delivery_note': delivery_note_item[1] if delivery_note_item[1] else '',
						'discount_percentage': insurance_details.discount, 'insurance_claim_coverage': insurance_details.coverage,
						'insurance_approval_number': delivery_note.insurance_approval_number if delivery_note.insurance_approval_number else ''}
						if insurance_details.rate:
							invoice_item['rate'] = insurance_details.rate,
						item_to_invoice.append(invoice_item)
					else:
						item_to_invoice.append({'reference_dt': "Delivery Note", 'reference_dn': delivery_note_item[1] if delivery_note_item[1] else '',
						'item_code': dn_item.item_code, 'rate': dn_item.rate, 'qty': dn_item.qty, 'item_name':dn_item.item_name,
						'cost_center': cost_center if cost_center else dn_item.cost_center,
						'delivery_note': delivery_note_item[1] if delivery_note_item[1] else ''})

			inpatient_services = frappe.db.sql("""select io.name, io.parent from `tabInpatient Record` ip,
			`tabInpatient Occupancy` io where ip.patient=%s and io.parent=ip.name and
			io.left=1 and io.invoiced=0""", (patient.name))
			if inpatient_services:
				for inpatient_service in inpatient_services:
					inpatient_occupancy = frappe.get_doc("Inpatient Occupancy", inpatient_service[0])
					inpatient_record = frappe.get_doc("Inpatient Record", inpatient_service[1])
					service_unit_type = frappe.get_doc("Healthcare Service Unit Type", frappe.db.get_value("Healthcare Service Unit", inpatient_occupancy.service_unit, "service_unit_type"))
					service_unit_type_item_name= frappe.db.get_value("Item", service_unit_type.item, "item_name")
					if service_unit_type and service_unit_type.is_billable == 1:
						check_in = inpatient_occupancy.check_in
						if inpatient_occupancy.invoiced_to:
							check_in = inpatient_occupancy.invoiced_to
						hours_occupied = time_diff_in_hours(inpatient_occupancy.check_out, check_in)
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
							cost_center = False

							if inpatient_occupancy.service_unit:
								cost_center = frappe.db.get_value("Healthcare Service Unit", inpatient_occupancy.service_unit, "cost_center")
							insurance_details = False
							if include_in_insurance and inpatient_record.insurance:
								insurance_details = get_insurance_details(inpatient_record.insurance, service_unit_type.item, patient)
							if include_in_insurance and insurance_details:
								invoice_item={'reference_dt': 'Inpatient Occupancy', 'reference_dn': inpatient_occupancy.name,
								'item_code': service_unit_type.item, 'cost_center': cost_center if cost_center else '', 'qty': qty, 'item_name':service_unit_type_item_name,
								'discount_percentage': insurance_details.discount, 'insurance_claim_coverage': insurance_details.coverage, 'insurance_approval_number': inpatient_record.insurance_approval_number if inpatient_record.insurance_approval_number else ''}
								if insurance_details.rate:
									invoice_item['rate'] = insurance_details.rate,
								item_to_invoice.append(invoice_item)
							else:
								item_to_invoice.append({'reference_dt': 'Inpatient Occupancy', 'reference_dn': inpatient_occupancy.name, 'item_name':service_unit_type_item_name,
								'item_code': service_unit_type.item, 'cost_center': cost_center if cost_center else '', 'qty': qty})
			return item_to_invoice
		else:
			frappe.throw(_("The Patient {0} do not have customer reference to invoice").format(patient.name))

def service_item_and_practitioner_charge(doc):
	is_ip = doc_is_ip(doc)
	if is_ip:
		service_item = get_practitioner_service_item(doc.practitioner, "inpatient_visit_charge_item")
		if not service_item:
			service_item = get_healthcare_service_item("inpatient_visit_charge_item")
	else:
		service_item = get_practitioner_service_item(doc.practitioner, "op_consulting_charge_item")
		if not service_item:
			service_item = get_healthcare_service_item("op_consulting_charge_item")

	practitioner_event = False
	appointment_type = False
	if doc.doctype == "Patient Appointment":
		practitioner_event = doc.practitioner_event
		appointment_type = doc.appointment_type
	elif doc.doctype == "Patient Encounter" and doc.appointment:
		practitioner_event, appointment_type = frappe.db.get_values("Patient Appointment", doc.appointment, ["practitioner_event", "appointment_type"])[0]
	practitioner_charge = get_practitioner_charge(doc.practitioner, is_ip, practitioner_event, appointment_type)

	# service_item required if practitioner_charge is valid
	if practitioner_charge and not service_item:
		throw_config_service_item(is_ip)

	return service_item, practitioner_charge

def throw_config_service_item(is_ip):
	service_item_lable = "Out Patient Consulting Charge Item"
	if is_ip:
		service_item_lable = "Inpatient Visit Charge Item"

	msg = _(("Please Configure {0} in ").format(service_item_lable) \
		+ """<b><a href="#Form/Healthcare Settings">Healthcare Settings</a></b>""")
	frappe.throw(msg)

def get_practitioner_service_item(practitioner, service_item_field):
	return frappe.db.get_value("Healthcare Practitioner", practitioner, service_item_field)

def get_healthcare_service_item(service_item_field):
	return frappe.db.get_value("Healthcare Settings", None, service_item_field)

def doc_is_ip(doc):
	is_ip = False
	if doc.inpatient_record:
		is_ip = True
	return is_ip

def get_practitioner_charge(practitioner, is_ip, practitioner_event=False, appointment_type=False):
	practitioner_charge_field = "op_consulting_charge"
	if is_ip:
		practitioner_charge_field = "inpatient_visit_charge"
	practitioner_charge = False
	if practitioner_event:
		practitioner_charge = frappe.db.get_value("Practitioner Event", practitioner_event, practitioner_charge_field)
	if not practitioner_charge:
		practitioner_charge = frappe.db.get_value("Appointment Type", appointment_type, practitioner_charge_field)
	if not practitioner_charge:
		practitioner_charge = frappe.db.get_value("Healthcare Practitioner", practitioner, practitioner_charge_field)

	return practitioner_charge if practitioner_charge else False

def manage_invoice_submit_cancel(doc, method):
	if doc.items:
		jv_amount = {}
		for item in doc.items:
			if item.get("reference_dt") and item.get("reference_dn"):
				if frappe.get_meta(item.reference_dt).has_field("invoiced"):
					set_invoiced(item, method, doc.name)
				if frappe.get_meta(item.reference_dt).has_field("insurance"):
					manage_insurance_invoice_on_submit(item.reference_dt, item.reference_dn, jv_amount,	item.item_code, item.amount)
				elif item.reference_dt in  ['Lab Prescription', 'Procedure Prescription', 'Inpatient Occupancy', 'Drug Prescription']:
					reference_obj = frappe.get_doc(item.reference_dt, item.reference_dn)
					if frappe.get_meta(reference_obj.parenttype).has_field("insurance"):
						manage_insurance_invoice_on_submit(reference_obj.parenttype, reference_obj.parent, jv_amount,	item.item_code, item.amount)
		if jv_amount and method == "on_submit":
			for key in jv_amount:
				create_insurance_claim(frappe.get_doc("Insurance Assignment", key), jv_amount[key], doc)
	if method=="on_submit" and frappe.db.get_value("Healthcare Settings", None, "create_test_on_si_submit") == '1':
		create_multiple("Sales Invoice", doc.name)
	manage_revenue_sharing(doc, method)

def manage_revenue_sharing(doc, method):
	if method == "on_submit":
		allocations = {}
		revenue_allocation = None
		#CREATE ALLOCATIONS
		for item in doc.items:
			if item.reference_dt and item.reference_dn and item.reference_dt != "Delivery Note" and not item.delivery_note:
				ref_doc = frappe.get_doc(item.reference_dt, item.reference_dn)
				item_group = item.item_group
				source = False
				practitioner = False
				if "Prescription" in item.reference_dt:
					source, practitioner = frappe.db.get_value("Patient Encounter",
						ref_doc.parent,	["source", "practitioner"])
				elif "Inpatient Occupancy" in item.reference_dt:
					source, practitioner = frappe.db.get_value("Inpatient Record",
						ref_doc.parent,	["source", "primary_practitioner"])
				else:
					practitioner = ref_doc.practitioner
					source = ref_doc.source
				if not source:
					continue
				for dist in doc.practitioner_revenue_distributions:
					if dist.reference_dt == item.reference_dt and dist.reference_dn == item.reference_dn and \
						dist.item_code == item.item_code and item.amount > 0 and dist.amount > 0:

						item_amount=0
						allow_split = frappe.db.get_value("Healthcare Settings", None, "practitioner_charge_separately")
						if allow_split:
							split_amount=0
							for split_item in doc.items:
								if split_item.reference_dt== item.reference_dt and split_item.reference_dn == item.reference_dn and \
									split_item.item_code != item.item_code and split_item.amount > 0:
									split_amount=split_amount + split_item.amount
							item_amount= split_amount + item.amount
						else:
							item_amount=item.amount

						revenue_allocation = None
						percentage = dist.amount / item_amount * 100
						if percentage > 0:
							if not revenue_allocation or revenue_allocation.practitioner != dist.practitioner:
								revenue_allocation = get_revenue_allocation(allocations, dist.practitioner)
							revenue_allocation.append("revenue_items", {
								"item": item.item_code,
								"reference_dt": item.reference_dt,
								"reference_dn": item.reference_dn,
								"invoice_amount": item_amount,
								"percentage": percentage,
								"amount": item_amount * percentage * .01
							})
							allocations[dist.practitioner] = revenue_allocation
		for practitioner in allocations:
			allocation = allocations[practitioner]
			entry = None
			if not allocation.revenue_items:
				continue
			# CREATE ADDITIONAL SLAARY OR PURCHASE INVOICE FOR EACH PRACTITIONER
			else:
				ptype, emp, sup = frappe.db.get_value("Healthcare Practitioner",
					practitioner,	["healthcare_practitioner_type", "employee", "supplier"])

				total_amount = get_total_revenue_share(allocation)
				if total_amount:
					if ptype == "External":
						inv_item = frappe.db.get_value("Healthcare Settings",
							None, "revenue_booking_item")

						if not sup or not inv_item:
							frappe.throw("Missing required configurations to process revenue allocation, Supplier / Revenue Booking Item")
						entry = create_purchase_invoice(doc, sup, inv_item, total_amount)
					else:
						sc = frappe.db.get_value("Healthcare Settings", None,
							"revenue_booking_salary_compnent")

						if not emp or not sc:
							frappe.throw("Missing required configurations to process revenue allocation, Employee / Salary Component")
						entry = create_additional_salary(doc.company, emp, sc, total_amount)
					if entry:
						allocation.sales_invoice = doc.name
						allocation.patient = doc.patient
						allocation.allocation_date = getdate()
						allocation.allocation_time = nowtime()
						allocation.reference_dt = entry.doctype
						allocation.reference_dn = entry.name
						allocation.total_amount = total_amount
						allocation.insert(ignore_permissions=1)
						if allocation.practitioner == practitioner:
							allocation.status = "Completed"
							allocation.submit()
						else:
							# mismatch in data! alert user role
							allocation.status = "Pending"
							allocation.save()
	elif method == "on_cancel":
		# cancel related Additional Salary or Purchase Invoice
		allocations = frappe.get_all("Healthcare Service Revenue Allocation",
			{"sales_invoice": doc.name}, ["name", "reference_dt", "reference_dn"])
		if allocations:
			for alloc in allocations:
				try:
					frappe.get_doc("Healthcare Service Revenue Allocation", alloc.name).cancel()
					frappe.get_doc(alloc.reference_dt, alloc.reference_dn).cancel()
				except Exception:
					# log error and warn
					frappe.throw("Did not Cancel, failed to process revenue allocation lnked to this Invoice")

def get_total_revenue_share(alloc):
	amount = 0
	for item in alloc.revenue_items:
		amount += item.amount
	return amount

def get_revenue_allocation(allocations, practitioner):
	if allocations.get(practitioner) and allocations[practitioner]:
		return allocations[practitioner]
	else:
		revenue_alloc = frappe.new_doc("Healthcare Service Revenue Allocation")
		revenue_alloc.practitioner = practitioner
		return revenue_alloc

def create_purchase_invoice(doc, supplier, item, amount):
	item_name, item_uom = frappe.db.get_value("Item", {"name": item},
		["item_name", "stock_uom"])
	pi = frappe.new_doc("Purchase Invoice")
	pi.posting_date = getdate()
	pi.supplier = supplier
	pi.company = doc.company
	pi.sch_sales_invoice=doc.name
	pi.update_stock = 0
	pi.is_paid = 0
	pi.append("items", {
			"item_code": item,
			"item_name": item_name,
			"qty": 1,
			"stock_uom": item_uom,
			"rate": amount
		})
	default_taxes_and_charge = frappe.db.exists(
		"Purchase Taxes and Charges Template",
		{
			"is_default": True,
			'company': doc.company
		}
	)
	if default_taxes_and_charge:
		pi.taxes_and_charges = default_taxes_and_charge
		taxes_and_charges = frappe.get_doc("Purchase Taxes and Charges Template", pi.taxes_and_charges)
		for tax in taxes_and_charges.taxes:
			tax_item = pi.append('taxes')
			tax_item.category = tax.category
			tax_item.add_deduct_tax = tax.add_deduct_tax
			tax_item.charge_type = tax.charge_type
			tax_item.included_in_print_rate = tax.included_in_print_rate
			tax_item.rate = tax.rate
			tax_item.account_head = tax.account_head
			tax_item.cost_center = tax.cost_center
			tax_item.description = tax.description
	pi.set_missing_values(True)
	pi.save(ignore_permissions=True)
	pi.submit()
	return pi

def create_additional_salary(company, employee, component, amount):
	additional_salary = frappe.get_doc({
		"doctype": "Additional Salary",
		"employee": employee,
		"payroll_date": getdate(),
		"amount": amount,
		"salary_component": component,
		"company": company
	}).insert(ignore_permissions=1)
	additional_salary.submit()
	return additional_salary

def set_invoiced(item, method, ref_invoice=None):
	invoiced = False
	if(method=="on_submit"):
		# if not item.delivery_note:
			# validate_invoiced_on_submit(item)
		invoiced = True

	if item.reference_dt == 'Inpatient Occupancy' and frappe.db.get_value("Healthcare Settings", None, "auto_invoice_inpatient") == '1':
		inpatient_occupancy = frappe.get_doc("Inpatient Occupancy", item.reference_dn)
		if inpatient_occupancy.left == 1:
			inpatient_occupancy.invoiced = invoiced
			inpatient_occupancy.save(ignore_permissions=True)
	elif not item.delivery_note:
		frappe.db.set_value(item.reference_dt, item.reference_dn, "invoiced", invoiced)

	if item.reference_dt == 'Patient Appointment':
		if frappe.db.get_value('Patient Appointment', item.reference_dn, 'procedure_template'):
			dt_from_appointment = "Clinical Procedure"
		elif frappe.db.get_value('Patient Appointment', item.reference_dn, 'radiology_procedure'):
			dt_from_appointment = "Radiology Examination"
		else:
			manage_fee_validity(item.reference_dn, method, ref_invoice)
			dt_from_appointment = "Patient Encounter"
		manage_doc_for_appoitnment(dt_from_appointment, item.reference_dn, invoiced)

	elif item.reference_dt == 'Lab Prescription':
		manage_prescriptions(invoiced, item.reference_dt, item.reference_dn, "Lab Test", "lab_test_created")

	elif item.reference_dt == 'Procedure Prescription':
		manage_prescriptions(invoiced, item.reference_dt, item.reference_dn, "Clinical Procedure", "procedure_created")

def validate_invoiced_on_submit(item):
	if frappe.db.get_value(item.reference_dt, item.reference_dn, "invoiced") == 1:
		msg_print(_("The item referenced by {0} - {1} is already invoiced"\
		).format(item.reference_dt, item.reference_dn))


def manage_prescriptions(invoiced, ref_dt, ref_dn, dt, created_check_field):
	created = frappe.db.get_value(ref_dt, ref_dn, created_check_field)
	if created == 1:
		# Fetch the doc created for the prescription
		doc_created = frappe.db.get_value(dt, {'prescription': ref_dn})
		frappe.db.set_value(dt, doc_created, 'invoiced', invoiced)

def validity_exists(practitioner, patient):
	return frappe.db.exists({
			"doctype": "Fee Validity",
			"practitioner": practitioner,
			"patient": patient})

def manage_fee_validity(appointment_name, method, ref_invoice=None):
	appointment_doc = frappe.get_doc("Patient Appointment", appointment_name)
	validity_exist = validity_exists(appointment_doc.practitioner, appointment_doc.patient)
	do_not_update = False
	visited = 0
	if validity_exist:
		fee_validity = frappe.get_doc("Fee Validity", validity_exist[0][0])
		# Check if the validity is valid
		if (fee_validity.valid_till >= appointment_doc.appointment_date):
			if (method == "on_cancel" and appointment_doc.status != "Closed"):
				if ref_invoice == fee_validity.ref_invoice:
					visited = fee_validity.visited - 1
					if visited < 0:
						visited = 0
					frappe.db.set_value("Fee Validity", fee_validity.name, "visited", visited)
				do_not_update = True
			elif (method == "on_submit" and fee_validity.visited < fee_validity.max_visit):
				visited = fee_validity.visited + 1
				frappe.db.set_value("Fee Validity", fee_validity.name, "visited", visited)
				do_not_update = True
			else:
				do_not_update = False

		if not do_not_update:
			fee_validity = update_fee_validity(fee_validity, appointment_doc.appointment_date, ref_invoice)
			visited = fee_validity.visited
	else:
		fee_validity = create_fee_validity(appointment_doc.practitioner, appointment_doc.patient, appointment_doc.appointment_date, ref_invoice)
		visited = fee_validity.visited

	# Mark All Patient Appointment invoiced = True in the validity range do not cross the max visit
	if (method == "on_cancel"):
		invoiced = True
	else:
		invoiced = False

	patient_appointments = appointments_valid_in_fee_validity(appointment_doc, invoiced)
	if patient_appointments and fee_validity:
		visit = visited
		for appointment in patient_appointments:
			if (method == "on_cancel" and appointment.status != "Closed"):
				if ref_invoice == fee_validity.ref_invoice:
					visited = visited - 1
					if visited < 0:
						visited = 0
					frappe.db.set_value("Fee Validity", fee_validity.name, "visited", visited)
				frappe.db.set_value("Patient Appointment", appointment.name, "invoiced", False)
				manage_doc_for_appoitnment("Patient Encounter", appointment.name, False)
			elif method == "on_submit" and int(fee_validity.max_visit) > visit:
				if ref_invoice == fee_validity.ref_invoice:
					visited = visited + 1
					frappe.db.set_value("Fee Validity", fee_validity.name, "visited", visited)
				frappe.db.set_value("Patient Appointment", appointment.name, "invoiced", True)
				manage_doc_for_appoitnment("Patient Encounter", appointment.name, True)
			if ref_invoice == fee_validity.ref_invoice:
				visit = visit + 1

	if method == "on_cancel":
		ref_invoice_in_fee_validity = frappe.db.get_value("Fee Validity", fee_validity.name, 'ref_invoice')
		if ref_invoice_in_fee_validity == ref_invoice:
			frappe.delete_doc("Fee Validity", fee_validity.name)

def appointments_valid_in_fee_validity(appointment, invoiced):
	valid_days = frappe.db.get_value("Healthcare Settings", None, "valid_days")
	max_visit = frappe.db.get_value("Healthcare Settings", None, "max_visit")
	if int(max_visit) < 1:
		max_visit = 1
	valid_days_date = add_days(getdate(appointment.appointment_date), int(valid_days))
	return frappe.get_list("Patient Appointment",{'patient': appointment.patient, 'invoiced': invoiced,
	'appointment_date':("<=", valid_days_date), 'appointment_date':(">=", getdate(appointment.appointment_date)),
	'practitioner': appointment.practitioner}, order_by="appointment_date", limit=int(max_visit)-1)

def manage_doc_for_appoitnment(dt_from_appointment, appointment, invoiced):
	dn_from_appointment = frappe.db.exists(
		dt_from_appointment,
		{
			"appointment": appointment
		}
	)
	if dn_from_appointment:
		frappe.db.set_value(dt_from_appointment, dn_from_appointment, "invoiced", invoiced)

def get_doc_for_appointment(doctype, appointment_id):
	docname = frappe.db.exists(
		doctype,
		{
			"appointment": appointment_id,
		}
	)
	if docname:
		return frappe.get_doc(doctype, docname)
	return False

@frappe.whitelist()
def get_drugs_to_invoice(encounter):
	encounter = frappe.get_doc("Patient Encounter", encounter)
	if encounter:
		patient = frappe.get_doc("Patient", encounter.patient)
		if patient and patient.customer:
				item_to_invoice = []
				for drug_line in encounter.drug_prescription:
					if drug_line.drug_code:
						item_name=frappe.db.get_value("Item", drug_line.drug_code, "item_name")
						qty = 1
						if frappe.db.get_value("Item", drug_line.drug_code, "stock_uom") == "Nos":
							qty = drug_line.get_quantity()
						description = False
						if drug_line.dosage:
							description = drug_line.dosage
						if description and drug_line.period:
							description += " for "+drug_line.period
						if not description:
							description = ""
						if encounter.insurance:
							insurance_details = get_insurance_details(encounter.insurance, drug_line.drug_code, patient)
							invoice_item={'reference_dt': 'Drug Prescription', 'reference_dn': drug_line.name, 'item_name':item_name,
								'item_code': drug_line.drug_code, 'qty': qty, 'description': description,
								'discount_percentage': insurance_details.discount, 'insurance_claim_coverage': insurance_details.coverage, 'insurance_approval_number': encounter.insurance_approval_number if encounter.insurance_approval_number else ''}
							if insurance_details.rate:
								invoice_item['rate'] = insurance_details.rate,
							item_to_invoice.append(invoice_item)
						else:
							item_to_invoice.append({'reference_dt': 'Drug Prescription', 'reference_dn': drug_line.name, 'item_name': item_name,
							'item_code': drug_line.drug_code, 'qty': qty, 'description': description})
				return item_to_invoice

@frappe.whitelist()
def get_children(doctype, parent, company, is_root=False):
	parent_fieldname = 'parent_' + doctype.lower().replace(' ', '_')
	fields = [
		'name as value',
		'is_group as expandable',
		'lft',
		'rgt'
	]
	# fields = [ 'name', 'is_group', 'lft', 'rgt' ]
	filters = [['ifnull(`{0}`,"")'.format(parent_fieldname), '=', '' if is_root else parent]]

	if is_root:
		fields += ['service_unit_type'] if doctype == 'Healthcare Service Unit' else []
		filters.append(['company', '=', company])

	else:
		fields += ['service_unit_type', 'allow_appointments', 'inpatient_occupancy', 'status'] if doctype == 'Healthcare Service Unit' else []
		fields += [parent_fieldname + ' as parent']

	hc_service_units = frappe.get_list(doctype, fields=fields, filters=filters)

	if doctype == 'Healthcare Service Unit':
		for each in hc_service_units:
			occupancy_msg = ""
			if each['expandable'] == 1:
				vacant = False
				total_bed = 0
				child_list = frappe.db.sql("""
					select name, status from `tabHealthcare Service Unit`
					where inpatient_occupancy = 1 and
					lft > %s and rgt < %s""",
					(each['lft'], each['rgt']))
				for child in child_list:
					total_bed += 1
					if not vacant:
						vacant = 0
					if child[1] == "Vacant":
						vacant += 1
				if vacant:
					occupancy_msg = str(vacant) + _(" Vacant out of ") + str(total_bed)
			each["occupied_out_of_vacant"] = occupancy_msg
	return hc_service_units

@frappe.whitelist()
def exists_appointment(appointment_date, practitioner, patient, not_in_status=["Cancelled"]):
	exist_appointment = frappe.db.get_list("Patient Appointment",
		{
			"practitioner": practitioner,
			"appointment_date": getdate(appointment_date),
			"patient": patient,
			"status": ["not in", not_in_status]
		}, ["name"])
	if exist_appointment:
		return exist_appointment[0]['name']
	return False

@frappe.whitelist()
def render_docs_as_html(docs):
	# docs key value pair {doctype: docname}
	docs_html = "<div class='col-md-12 col-sm-12 text-muted'>"
	for doc in docs:
		docs_html += render_doc_as_html(doc['doctype'], doc['docname'])['html'] + "<br/>"
		return {'html': docs_html}

@frappe.whitelist()
def render_doc_as_html(doctype, docname, exclude_fields = []):
	#render document as html, three column layout will break
	doc = frappe.get_doc(doctype, docname)
	meta = frappe.get_meta(doctype)
	doc_html = "<div class='col-md-12 col-sm-12'>"
	section_html = ""
	section_label = ""
	html = ""
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
			section_html = ""
			html = ""
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
			html = ""
			col_on += 1
			if df.label:
				html += '<br>' + df.label
			continue
		#on table iterate in items and create table based on in_list_view, append to section html or doc html
		if df.fieldtype == "Table":
			items = doc.get(df.fieldname)
			if not items: continue
			child_meta = frappe.get_meta(df.options)
			if not has_data : has_data = True
			table_head = ""
			table_row = ""
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
				section_html += '<table class="table table-condensed \
				bordered">' + table_head +  table_row + '</table>'
			else:
				html += '<table class="table table-condensed table-bordered">' \
				+ table_head +  table_row + '</table>'
			continue
		#on other field types add label and value to html
		if not df.hidden and not df.print_hide and doc.get(df.fieldname) and df.fieldname not in exclude_fields:
			html +=  "<br>{0} : {1}".format(df.label or df.fieldname, \
			doc.get(df.fieldname))
			if not has_data : has_data = True
	if sec_on and col_on and has_data:
		doc_html += section_html + html + "</div></div>"
	elif sec_on and not col_on and has_data:
		doc_html += "<div class='col-md-12 col-sm-12'\
		><div class='col-md-12 col-sm-12'>" \
		+ section_html + html +"</div></div>"

	return {'html': doc_html}

@frappe.whitelist()
def get_patient_vitals(patient, from_date=None, to_date=None):
	if not patient: return
	vitals = frappe.db.sql("""select * from `tabVital Signs` where \
	docstatus=1 and patient=%s order by signs_date, signs_time""", \
	(patient), as_dict=1)
	if vitals and vitals[0]:
		return vitals
	else:
		return False

@frappe.whitelist()
def disable_enable_template(doctype, docname, item_code, disabled):
	frappe.db.set_value(doctype, docname, "disabled", disabled)
	if (frappe.db.exists({ #set Item's disabled field to status
		"doctype": "Item",
		"item_code": item_code})):
			frappe.db.set_value("Item", item_code, "disabled", disabled)
	return

@frappe.whitelist()
def change_item_code_from_doc(item_code, doc):
	args = json.loads(doc)
	doc = frappe._dict(args)
	if(frappe.db.exists({
		"doctype": "Item",
		"item_code": item_code})):
		frappe.throw(_("Code {0} already exist").format(item_code))
	else:
		frappe.rename_doc("Item", doc.item_code, item_code, ignore_permissions = True)
		frappe.db.set_value(doc.doctype, doc.name, "item_code", item_code)
	return

def create_item_from_doc(doc, item_name):
	if(doc.is_billable == 1):
		disabled = 0
	else:
		disabled = 1
	#insert item
	item =  frappe.get_doc({
	"doctype": "Item",
	"item_code": doc.item_code,
	"item_name": item_name,
	"item_group": doc.item_group,
	"description": doc.description,
	"is_sales_item": 1,
	"is_service_item": 1,
	"is_purchase_item": 0,
	"is_stock_item": 0,
	"show_in_website": 0,
	"is_pro_applicable": 0,
	"disabled": disabled,
	"stock_uom": "Unit"
	}).insert(ignore_permissions=True)

	#insert item price
	#get item price list to insert item price
	if(doc.rate != 0.0):
		price_list_name = frappe.db.get_value("Selling Settings", None, "selling_price_list")
		if not price_list_name:
			price_list_name = frappe.db.get_value("Price List", {"selling": 1})
		if price_list_name:
			if(doc.rate):
				make_item_price(item.name, price_list_name, doc.rate)
			else:
				make_item_price(item.name, price_list_name, 0.0)
	#Set item to the template
	frappe.db.set_value(doc.doctype, doc.name, "item", item.name)

	doc.reload() #refresh the doc after insert.

def make_item_price(item, price_list_name, item_price):
	frappe.get_doc({
		"doctype": "Item Price",
		"price_list": price_list_name,
		"item_code": item,
		"price_list_rate": item_price
	}).insert(ignore_permissions=True)

def update_item_from_doc(doc, item_name):
	if(doc.is_billable == 1 and doc.item):
		updating_item(doc, item_name)
		if(doc.rate != 0.0):
			updating_rate(doc, item_name)
	elif(doc.is_billable == 0 and doc.item):
		frappe.db.set_value("Item", doc.item, "disabled", 1)

def updating_item(doc, item_name):
	frappe.db.sql("""update `tabItem` set item_name=%s, item_group=%s, disabled=0,
		description=%s, modified=NOW() where item_code=%s""",
		(item_name, doc.item_group , doc.description, doc.item))

def updating_rate(doc, item_name):
	frappe.db.sql("""update `tabItem Price` set item_name=%s, price_list_rate=%s, modified=NOW() where
	 item_code=%s""",(item_name, doc.rate, doc.item))

def on_trash_doc_having_item_reference(doc):
	if(doc.item):
		try:
			frappe.delete_doc("Item",doc.item)
		except Exception:
			frappe.throw(_("Not permitted. Please disable the {0}").format(doc.doctype))

def exist_invoice_item_for_healthcare_doc(doctype, docname):
	return frappe.db.exists(
		"Sales Invoice Item",
		{
			"reference_dt": doctype,
			"reference_dn": docname
		}
	)

def valid_insurance(insurance, posting_date):
	healthcare_insurance = frappe.get_doc("Insurance Assignment", insurance)
	if frappe.db.exists("Insurance Contract",
		{
			'insurance_company': healthcare_insurance.insurance_company,
			'start_date':("<=", getdate(posting_date)),
			'end_date':(">=", getdate(posting_date)),
			'is_active': 1
		}):
		if frappe.db.exists("Insurance Assignment",
			{
				'name': insurance,
				'end_date':(">=", getdate(posting_date)),
				'is_active': 1
			}):
			return True
	return False


def get_insurance_details(insurance, service_item, patient):
	rate = False
	discount = 0
	coverage = 0
	healthcare_insurance = frappe.get_doc("Insurance Assignment", insurance)
	service_item_group = frappe.get_value("Item", service_item, "item_group")
	if healthcare_insurance and valid_insurance(healthcare_insurance.name,nowdate()):
		insurance_contract = frappe.get_doc("Insurance Contract",
			{
				"insurance_company": healthcare_insurance.insurance_company,
				"is_active": 1
			}
		)
		item_price = frappe.db.exists("Item Price",
		{
			'item_code': service_item,
			'price_list': insurance_contract.price_list
		})
		if item_price:
			discount = insurance_contract.discount
			for item in insurance_contract.insurance_contract_discount:
				if service_item_group== item.item_group:
					discount=item.discount
			rate= frappe.db.get_value("Item Price", item_price, 'price_list_rate')
			coverage = healthcare_insurance.coverage
			if patient.inpatient_record and healthcare_insurance.ip_coverage:
				coverage = healthcare_insurance.ip_coverage

	return frappe._dict({'rate': rate, 'discount': discount, 'coverage': coverage})

def manage_insurance_invoice_on_submit(reference_dt, reference_dn, jv_amount, app_service_item, amount):
	insurance = frappe.db.get_value(reference_dt, reference_dn, 'insurance')
	if insurance and amount:
		if insurance in jv_amount:
			jv_amount[insurance] += amount
		else:
			jv_amount[insurance] = amount
	return jv_amount

def manage_insurance_claim_on_si_cancel(doc):
	claim = frappe.db.exists("Insurance Claim",
			{
				'sales_invoice': doc.name
			})
	if claim:
		claim_obj = frappe.get_doc("Insurance Claim", claim)
		if claim_obj.claim_status=="Claim Created":
			claim_obj.cancel()
			frappe.db.set_value("Insurance Claim", claim_obj.name, "claim_status", "Cancelled")
def create_insurance_claim(insurance, amount, doc):
	insurance_claim=frappe.new_doc('Insurance Claim')
	insurance_claim.patient=doc.patient
	insurance_claim.insurance_company=insurance.insurance_company
	insurance_claim.insurance_assignment=insurance.name
	if doc.inpatient_record and insurance.ip_coverage:
		insurance_claim.claim_percentage=insurance.ip_coverage
		insurance_claim.claim_amount=amount*0.01*insurance.ip_coverage
	else:
		insurance_claim.claim_percentage=insurance.coverage
		insurance_claim.claim_amount=amount*0.01*insurance.coverage
	insurance_claim.bill_amount=amount
	insurance_claim.created_by=frappe.session.user
	insurance_claim.created_on=nowdate()
	insurance_claim.sales_invoice=doc.name
	insurance_claim.claim_status="Claim Created"
	insurance_claim_item=[]
	for item in doc.items:
		if item.reference_dt:
			if frappe.get_meta(item.reference_dt).has_field("insurance"):
				reference_doc = frappe.get_doc(item.reference_dt, item.reference_dn)
			elif item.reference_dt in  ['Lab Prescription', 'Procedure Prescription', 'Inpatient Occupancy', 'Drug Prescription']:
				reference_obj = frappe.get_doc(item.reference_dt, item.reference_dn)
				if frappe.get_meta(reference_obj.parenttype).has_field("insurance"):
					reference_doc = frappe.get_doc(reference_obj.parenttype,  reference_obj.parent)
			if reference_doc.insurance and reference_doc.insurance== insurance.name :
				insurance_remarks=''
				if frappe.db.has_column(item.reference_dt, 'insurance_remarks'):
					insurance_remarks = reference_doc.insurance_remarks
				insurance_claim_item.append({
								"patient": doc.patient,
								"insurance_company": insurance.insurance_company,
								"insurance_assignment": insurance.name,
								"sales_invoice": doc.name,
								"date_of_service": doc.posting_date,
								"item_code": item.item_code,
								"item_name": item.item_name,
								"discount_percentage": item.discount_percentage,
								"discount_amount": item.discount_amount,
								"rate": item.rate,
								"amount": item.amount,
								"insurance_claim_coverage": item.insurance_claim_coverage,
								"insurance_claim_amount": item.insurance_claim_amount,
								"claim_status":"Claim Created",
								"insurance_approval_number": item.insurance_approval_number,
								"insurance_remarks": insurance_remarks if insurance_remarks else '',
							})
	insurance_claim.set("insurance_claim_item", insurance_claim_item)
	insurance_claim.save(ignore_permissions = True)
	insurance_claim.submit()

def get_insurance_approval_number(doc):
	approval_number=False
	for item in doc.items:
		if item.insurance_approval_number:
			if not approval_number:
				approval_number = item.insurance_approval_number
			else:
				approval_number += ", " + item.insurance_approval_number
	return approval_number if approval_number else ''

@frappe.whitelist()
def get_sales_invoice_for_healthcare_doc(doctype, docname):
	sales_item_exist = exist_invoice_item_for_healthcare_doc(doctype, docname)
	if sales_item_exist:
		return frappe.get_doc("Sales Invoice", frappe.db.get_value("Sales Invoice Item", sales_item_exist, "parent"))
	return False

@frappe.whitelist()
def sales_item_details_for_healthcare_doc(item_code, doc, wh=None):
	from six import string_types
	if isinstance(doc, string_types):
		doc =  json.loads(doc)
		if isinstance(doc, dict):
			doc = frappe._dict(doc)
	price_list = False
	if frappe.get_meta(doc.doctype).has_field("selling_price_list"):
		price_list = doc.selling_price_list
	if not price_list:
		price_list = frappe.db.get_value("Selling Settings", None, "selling_price_list")
	if not price_list:
		price_list = frappe.db.get_values("Price List", {"selling": 1}, ['name'])[0]
	price_list_currency = frappe.db.get_values("Price List", {"selling": 1, "name": price_list}, ['name', 'currency'])[0]
	args = {
		'doctype': "Sales Invoice",
		'item_code': item_code,
		'company': doc.company,
		'customer': frappe.db.get_value("Patient", doc.patient, "customer"),
		'selling_price_list': price_list,
		'price_list_currency': price_list_currency,
		'plc_conversion_rate': 1.0,
		'conversion_rate': 1.0
	}
	if wh:
		args['warehouse'] = wh
	item_details = get_item_details(args)
	return item_details if item_details else False

def get_procedure_delivery_item(patient, procedure=False):
	query = """
		select
			di.name, dn.name
		from
			`tabDelivery Note` dn, `tabDelivery Note Item` di
		where
			dn.patient=%s and di.parent=dn.name and dn.status='To Bill'
	"""
	if procedure:
		query += """and di.reference_dn=%s"""
		return frappe.db.sql(query, (patient, procedure))
	else:
		query += """and di.reference_dn is NULL"""
		return frappe.db.sql(query, (patient))

def item_reduce_procedure_rate(dn_item, procedure_items):
	for item in procedure_items:
		if item.item_code == dn_item.item_code:
			if item.invoice_additional_quantity_used:
				if dn_item.qty <= item.procedure_qty:
					return dn_item.qty*dn_item.rate
				else:
					return item.procedure_qty*dn_item.rate
			else:
				return dn_item.qty*dn_item.rate
	return 0

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

@frappe.whitelist()
def get_revenue_sharing_distribution(invoice_item):
	from six import string_types
	if isinstance(invoice_item, string_types):
		item = json.loads(invoice_item)
	else:
		item = invoice_item
	distributions = []
	if item.reference_dt and item.reference_dn:
		not_share_revenue_dt = ["Inpatient Record Procedure", "Inpatient Occupancy", "Lab Prescription", "Procedure Prescription", "Radiology Procedure Prescription", "Drug Prescription",]
		if not item.delivery_note and item.reference_dt != "Delivery Note" and item.reference_dt not in not_share_revenue_dt:
			ref_doc = frappe.get_doc(item.reference_dt, item.reference_dn)
			if ref_doc.source == "Direct":
				assignment = frappe.db.exists("Healthcare Service Profile Assignment",
					{
						"practitioner": ref_doc.practitioner,
						"is_active": 1
					}
				)
				if assignment:
					assignment_doc=frappe.get_doc("Healthcare Service Profile Assignment", assignment)
					if assignment_doc:
						distribute_amount=0
						item_amount= item.rate * item.qty
						if assignment_doc.revenue_sharing_items:
							item_group=frappe.db.get_value("Item", item.item_code, "item_group")
							for sharing_item in assignment_doc.revenue_sharing_items:
								if sharing_item.item_group==item_group:
									if sharing_item.type_of_sharing=="Fixed":
										distribute_amount=sharing_item.direct_amount
									else:
										distribute_amount=(item_amount * 0.01 * sharing_item.direct_percentage)
									distribution = {
										'item_code': item.item_code,
										'item_amount': item_amount,
										'reference_dt': item.reference_dt,
										'reference_dn': item.reference_dn,
										'type_of_sharing' : sharing_item.type_of_sharing,
										'amount': distribute_amount
									}
									distribution['practitioner'] = ref_doc.practitioner
									distributions.append(distribution)
			elif ref_doc.source == "Referral" and ref_doc.referring_practitioner:
				assignment = frappe.db.exists("Healthcare Service Profile Assignment",
					{
						"practitioner": ref_doc.referring_practitioner,
						"is_active": 1
					}
				)
				if assignment:
					assignment_doc=frappe.get_doc("Healthcare Service Profile Assignment", assignment)
					if assignment_doc:
						distribute_amount=0
						item_amount= item.rate * item.qty
						if assignment_doc.revenue_sharing_items:
							item_group=frappe.db.get_value("Item", item.item_code, "item_group")
							for sharing_item in assignment_doc.revenue_sharing_items:
								if sharing_item.item_group==item_group:
									if sharing_item.type_of_sharing=="Fixed":
										distribute_amount=sharing_item.referral_amount
									else:
										distribute_amount=(item_amount* 0.01 * sharing_item.referral_percentage)
									distribution = {
									'item_code': item.item_code,
									'item_amount': item_amount,
									'reference_dt': item.reference_dt,
									'reference_dn': item.reference_dn,
									'type_of_sharing' : sharing_item.type_of_sharing,
									'amount': distribute_amount}
									distribution['practitioner'] = ref_doc.referring_practitioner
									distributions.append(distribution)
					if assignment_doc.allow_multiple:
						distribute_amount=0
						item_amount= item.rate * item.qty
						if assignment_doc.revenue_sharing_items:
							item_group=frappe.db.get_value("Item", item.item_code, "item_group")
							for sharing_item in assignment_doc.revenue_sharing_items:
								if sharing_item.item_group==item_group:
									if sharing_item.type_of_sharing=="Fixed":
										distribute_amount=direct_amount
									else:
										distribute_amount=(item_amount* 0.01 * sharing_item.direct_percentage)
									distribution = {
									'item_code': item.item_code,
									'item_amount': item_amount,
									'reference_dt': item.reference_dt,
									'reference_dn': item.reference_dn,
									'type_of_sharing' : sharing_item.type_of_sharing,
									'amount': distribute_amount}
									distribution['practitioner'] = ref_doc.practitioner
									distributions.append(distribution)
			elif ref_doc.source == "External Referral" and ref_doc.referring_practitioner:
				assignment = frappe.db.exists("Healthcare Service Profile Assignment",
					{
						"practitioner": ref_doc.referring_practitioner,
						"is_active": 1
					}
				)
				if assignment:
					assignment_doc=frappe.get_doc("Healthcare Service Profile Assignment", assignment)
					if assignment_doc:
						distribute_amount=0
						item_amount= item.rate * item.qty
						if assignment_doc.revenue_sharing_items:
							item_group=frappe.db.get_value("Item", item.item_code, "item_group")
							for sharing_item in assignment_doc.revenue_sharing_items:
								if sharing_item.item_group==item_group:
									if sharing_item.type_of_sharing=="Fixed":
										distribute_amount=referral_amount
									else:
										distribute_amount=(item_amount* 0.01 * sharing_item.referral_percentage)
									distribution = {
									'item_code': item.item_code,
									'item_amount': item_amount,
									'reference_dt': item.reference_dt,
									'reference_dn': item.reference_dn,
									'type_of_sharing' : sharing_item.type_of_sharing,
									'amount': distribute_amount}
									distribution['practitioner'] = ref_doc.referring_practitioner
									distributions.append(distribution)
	return distributions

@frappe.whitelist()
def get_insurance_pricelist(insurance):
	price_list = False
	insurance_company_name=False
	if insurance:
		healthcare_insurance = frappe.get_doc("Insurance Assignment", insurance)
		if healthcare_insurance and valid_insurance(healthcare_insurance.name,nowdate()):
			insurance_contract = frappe.get_doc("Insurance Contract",
				{
					"insurance_company": healthcare_insurance.insurance_company,
					"is_active": 1
				}
			)
			price_list = insurance_contract.price_list
			insurance_company_name= healthcare_insurance.insurance_company_name
	return price_list,insurance_company_name