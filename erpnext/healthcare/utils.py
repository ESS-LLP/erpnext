# -*- coding: utf-8 -*-
# Copyright (c) 2018, earthians and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
import datetime
from frappe import _
import math
from frappe.utils import time_diff_in_hours, rounded, getdate, add_days, nowdate
from erpnext.healthcare.doctype.healthcare_settings.healthcare_settings import get_income_account
from erpnext.healthcare.doctype.fee_validity.fee_validity import create_fee_validity, update_fee_validity
from erpnext.healthcare.doctype.lab_test.lab_test import create_multiple
from erpnext.stock.get_item_details import get_item_details

@frappe.whitelist()
def get_healthcare_services_to_invoice(patient):
	patient = frappe.get_doc("Patient", patient)
	if patient:
		if patient.customer:
			item_to_invoice = []
			patient_appointments = frappe.get_list("Patient Appointment",{'patient': patient.name, 'invoiced': False},
			order_by="appointment_date")
			if patient_appointments:
				fee_validity_details = []
				valid_days = frappe.db.get_value("Healthcare Settings", None, "valid_days")
				max_visit = frappe.db.get_value("Healthcare Settings", None, "max_visit")
				for patient_appointment in patient_appointments:
					include_in_insurance = False
					cost_center = False
					patient_appointment_obj = frappe.get_doc("Patient Appointment", patient_appointment['name'])
					if patient_appointment_obj.insurance:
						include_in_insurance = True
					if patient_appointment_obj.service_unit:
						cost_center = frappe.db.get_value("Healthcare Service Unit", patient_appointment_obj.service_unit, "cost_center")
					if patient_appointment_obj.procedure_template:
						if frappe.db.get_value("Clinical Procedure Template", patient_appointment_obj.procedure_template, "is_billable") == 1:
							app_service_item = frappe.db.get_value("Clinical Procedure Template", patient_appointment_obj.procedure_template, "item")
							app_procedure_rate = False
							if include_in_insurance:
								app_procedure_rate, discount_percentage = get_insurance_deatils(patient_appointment_obj.insurance, app_service_item)
							if include_in_insurance and app_procedure_rate:
								item_to_invoice.append({'reference_type': 'Patient Appointment', 'reference_name': patient_appointment_obj.name,
									'service': app_service_item, 'cost_center': cost_center, 'rate': app_procedure_rate, 'discount_percentage': discount_percentage})
							else:
								item_to_invoice.append({'reference_type': 'Patient Appointment', 'reference_name': patient_appointment_obj.name,
									'service': app_service_item, 'cost_center': cost_center})
					elif patient_appointment_obj.radiology_procedure:
						if frappe.db.get_value("Radiology Procedure", patient_appointment_obj.radiology_procedure, "is_billable") == 1:
							app_radiology_service_item = frappe.db.get_value("Radiology Procedure", patient_appointment_obj.radiology_procedure, "item")
							app_radiology_rate = False
							if include_in_insurance:
									app_radiology_rate, discount_percentage = get_insurance_deatils(patient_appointment_obj.insurance, app_radiology_service_item)
									if include_in_insurance and app_radiology_rate:
										item_to_invoice.append({'reference_type': 'Patient Appointment', 'reference_name': patient_appointment_obj.name,
										'service': app_radiology_service_item, 'cost_center': cost_center, 'rate': app_radiology_rate, 'discount_percentage': discount_percentage})
									else:
										item_to_invoice.append({'reference_type': 'Patient Appointment', 'reference_name': patient_appointment_obj.name,
										'service': patient_appointment_obj.radiology_procedure, 'cost_center': cost_center})
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
						if not practitioner_charge: # skip billing if charge not configured
							skip_invoice = True

						if not skip_invoice:
							income_account = None
							discount_percentage = False
							if patient_appointment_obj.practitioner:
								income_account = get_income_account(patient_appointment_obj.practitioner, patient_appointment_obj.company)
							if include_in_insurance :
								discount_percentage = get_insurance_deatils(patient_appointment_obj.insurance, service_item)[1]
							if discount_percentage:
								item_to_invoice.append({'reference_type': 'Patient Appointment', 'reference_name': patient_appointment_obj.name,
									'service': service_item, 'cost_center': cost_center, 'rate': practitioner_charge, 'income_account': income_account,
									'discount_percentage': discount_percentage})
							else:
								item_to_invoice.append({'reference_type': 'Patient Appointment', 'reference_name': patient_appointment_obj.name,
									'service': service_item, 'cost_center': cost_center, 'rate': practitioner_charge, 'income_account': income_account})
			encounters = frappe.get_list("Patient Encounter", {'patient': patient.name, 'invoiced': False, 'docstatus': 1})
			if encounters:
				for encounter in encounters:
					include_in_insurance = False
					cost_center = False
					encounter_obj = frappe.get_doc("Patient Encounter", encounter['name'])
					if encounter_obj.service_unit:
						cost_center = frappe.db.get_value("Healthcare Service Unit", encounter_obj.service_unit, "cost_center")
					if encounter_obj.insurance:
						include_in_insurance = True
					if not encounter_obj.appointment:
						practitioner_charge = 0
						discount_percentage = False
						income_account = None
						service_item = None
						if encounter_obj.practitioner:
							service_item, practitioner_charge = service_item_and_practitioner_charge(encounter_obj)
							if not practitioner_charge: # skip billing if charge not configured
								continue
							income_account = get_income_account(encounter_obj.practitioner, encounter_obj.company)
						if include_in_insurance :
							discount_percentage = get_insurance_deatils(encounter_obj.insurance, service_item)[1]
						if discount_percentage:
							item_to_invoice.append({'reference_type': 'Patient Encounter', 'reference_name': encounter_obj.name,
							'service': service_item, 'rate': practitioner_charge, 'cost_center':cost_center, 'discount_percentage': discount_percentage,
							'income_account': income_account})
						else:
							item_to_invoice.append({'reference_type': 'Patient Encounter', 'reference_name': encounter_obj.name,
							'service': service_item, 'rate': practitioner_charge, 'cost_center':cost_center,
							'income_account': income_account})
			lab_tests = frappe.get_list("Lab Test", {'patient': patient.name, 'invoiced': False, 'docstatus': 1})
			if lab_tests:
				for lab_test in lab_tests:
					insurance_test_charge = False
					cost_center = False
					lab_test_obj = frappe.get_doc("Lab Test", lab_test['name'])
					if lab_test_obj.service_unit:
						cost_center = frappe.db.get_value("Healthcare Service Unit", lab_test_obj.service_unit, "cost_center")
					if lab_test_obj.insurance:
						insurance_test_charge, discount_percentage = get_insurance_deatils(lab_test_obj.insurance, frappe.db.get_value("Lab Test Template", lab_test_obj.template, "item"))
					if lab_test_obj.insurance and insurance_test_charge:
						if frappe.db.get_value("Lab Test Template", lab_test_obj.template, "is_billable") == 1:
							item_to_invoice.append({'reference_type': 'Lab Test', 'reference_name': lab_test_obj.name,
							'service': frappe.db.get_value("Lab Test Template", lab_test_obj.template, "item"), 'cost_center':cost_center,	'discount_percentage': discount_percentage,'rate':insurance_test_charge })
					else:
						if frappe.db.get_value("Lab Test Template", lab_test_obj.template, "is_billable") == 1:
							item_to_invoice.append({'reference_type': 'Lab Test', 'reference_name': lab_test_obj.name,
							'service': frappe.db.get_value("Lab Test Template", lab_test_obj.template, "item"), 'cost_center':cost_center})

			lab_rxs = frappe.db.sql("""select lp.name,et.name from `tabPatient Encounter` et, `tabLab Prescription` lp
			where et.patient=%s and lp.parent=et.name and lp.lab_test_created=0 and lp.invoiced=0""", (patient.name))
			if lab_rxs:
				for lab_rx in lab_rxs:
					include_in_insurance = False
					cost_center = False
					rx_obj = frappe.get_doc("Lab Prescription", lab_rx[0])
					if rx_obj.parenttype == "Patient Encounter":
						rx_obj_service_unit = frappe.get_value("Patient Encounter", rx_obj.parent, "service_unit")
						if rx_obj_service_unit:
							cost_center = frappe.db.get_value("Healthcare Service Unit", rx_obj_service_unit, "cost_center")
					encx_obj = frappe.get_doc("Patient Encounter", lab_rx[1])
					if encx_obj.insurance:
						include_in_insurance = True
					if rx_obj.lab_test_code and (frappe.db.get_value("Lab Test Template", rx_obj.lab_test_code, "is_billable") == 1):
						insurance_enc_charge = False
						discount_percentage = 0
						if include_in_insurance:
							insurance_enc_charge, discount_percentage = get_insurance_deatils(encx_obj.insurance, frappe.db.get_value("Lab Test Template", rx_obj.lab_test_code, "item"))
						if insurance_enc_charge:
							item_to_invoice.append({'reference_type': 'Lab Prescription', 'reference_name': rx_obj.name,
							'service': frappe.db.get_value("Lab Test Template", rx_obj.lab_test_code, "item"), 'cost_center':cost_center, 'discount_percentage': discount_percentage,	'rate':insurance_enc_charge})
						else:
							item_to_invoice.append({'reference_type': 'Lab Prescription', 'reference_name': rx_obj.name,
							'service': frappe.db.get_value("Lab Test Template", rx_obj.lab_test_code, "item"), 'cost_center':cost_center})

			procedures = frappe.get_list("Clinical Procedure", {'patient': patient.name, 'invoiced': False, 'status': 'Completed'})
			if procedures:
				for procedure in procedures:
					cost_center = False
					procedure_obj = frappe.get_doc("Clinical Procedure", procedure['name'])
					if procedure_obj.service_unit:
						cost_center = frappe.db.get_value("Healthcare Service Unit", procedure_obj.service_unit, "cost_center")
					if not procedure_obj.appointment and procedure_obj.procedure_template and (frappe.db.get_value("Clinical Procedure Template", procedure_obj.procedure_template, "is_billable") == 1):
						if procedure_obj.consume_stock:
							reduce_from_procedure_rate = 0
							delivery_note_items = get_procedure_delivery_item(patient.name, procedure_obj.name)
							if delivery_note_items:
								for delivery_note_item in delivery_note_items:
									dn_item = frappe.get_doc("Delivery Note Item", delivery_note_item[0])
									reduce_from_procedure_rate += item_reduce_procedure_rate(dn_item, procedure_obj.items)
									item_to_invoice.append({'reference_type': dn_item.reference_dt, 'reference_name': dn_item.reference_dn,
										'service': dn_item.item_code, 'rate': dn_item.rate, 'qty': dn_item.qty,
										'cost_center': cost_center if cost_center else '', 'delivery_note': delivery_note_item[1] if delivery_note_item[1] else ''})

						procedure_service_item = frappe.db.get_value("Clinical Procedure Template", procedure_obj.procedure_template, "item")
						procedure_rate = False
						discount_percentage = 0
						if procedure_obj.insurance :
							procedure_rate, discount_percentage = get_insurance_deatils(procedure_obj.insurance, procedure_service_item)
						if procedure_rate:
							item_to_invoice.append({'reference_type': 'Clinical Procedure', 'reference_name': procedure_obj.name,
							'service': procedure_service_item, 'cost_center':cost_center, 'rate': procedure_rate-reduce_from_procedure_rate,
							'discount_percentage': discount_percentage})
						else:
							item_to_invoice.append({'reference_type': 'Clinical Procedure', 'reference_name': procedure_obj.name, 'cost_center': cost_center if cost_center else '',
								'service': procedure_service_item, 'rate': float(procedure_obj.standard_selling_rate)-reduce_from_procedure_rate})

			procedure_rxs = frappe.db.sql("""select pp.name from `tabPatient Encounter` et,
			`tabProcedure Prescription` pp where et.patient=%s and pp.parent=et.name and
			pp.procedure_created=0 and pp.invoiced=0 and pp.appointment_booked=0""", (patient.name))
			if procedure_rxs:
				for procedure_rx in procedure_rxs:
					include_in_insurance = False
					cost_center = False
					rx_obj = frappe.get_doc("Procedure Prescription", procedure_rx[0])
					if rx_obj.parenttype == "Patient Encounter":
						rx_obj_service_unit = frappe.get_value("Patient Encounter", rx_obj.parent, "service_unit")
						if rx_obj_service_unit:
							cost_center = frappe.db.get_value("Healthcare Service Unit", rx_obj_service_unit, "cost_center")
					encx_obj = frappe.get_doc("Patient Encounter", procedure_rx[1])
					if encx_obj.insurance:
						include_in_insurance = True
					if frappe.db.get_value("Clinical Procedure Template", rx_obj.procedure, "is_billable") == 1:
						if include_in_insurance:
							insurance_enc_charge, discount_percentage = get_insurance_deatils(encx_obj.insurance, frappe.db.get_value("Clinical Procedure Template", rx_obj.procedure, "item"))
							item_to_invoice.append({'reference_type': 'Procedure Prescription', 'reference_name': rx_obj.name,
							'service': frappe.db.get_value("Clinical Procedure Template", rx_obj.procedure, "item"), 'cost_center': cost_center, 'rate': insurance_enc_charge, 'discount_percentage': discount_percentage})
						else:
							item_to_invoice.append({'reference_type': 'Procedure Prescription', 'reference_name': rx_obj.name,
							'service': frappe.db.get_value("Clinical Procedure Template", rx_obj.procedure, "item"), 'cost_center': cost_center})

			r_procedures = frappe.get_list("Radiology Examination", {'patient': patient.name, 'invoiced': False})
			if r_procedures:
				for procedure in r_procedures:
					include_in_insurance = False
					cost_center = False
					procedure_obj = frappe.get_doc("Radiology Examination", procedure['name'])
					if procedure_obj.service_unit:
						cost_center = frappe.db.get_value("Healthcare Service Unit", procedure_obj.service_unit, "cost_center")
					if not procedure_obj.appointment:
						if procedure_obj.radiology_procedure and (frappe.db.get_value("Radiology Procedure", procedure_obj.radiology_procedure, "is_billable") == 1):
							procedure_service_item = frappe.db.get_value("Radiology Procedure", procedure_obj.radiology_procedure, "item")
							procedure_rate = False
							if procedure_obj.insurance:
								include_in_insurance = True
								procedure_rate, discount_percentage = get_insurance_deatils(procedure_obj.insurance, procedure_service_item)
							if include_in_insurance and procedure_rate:
								item_to_invoice.append({'reference_type': 'Radiology Examination', 'reference_name': procedure_obj.name,
								'cost_center': cost_center if cost_center else '', 'service': procedure_service_item, 'rate': procedure_rate, 'discount_percentage': discount_percentage})
							else:
								item_to_invoice.append({'reference_type': 'Radiology Examination', 'reference_name': procedure_obj.name,
								'cost_center': cost_center if cost_center else '', 'service': procedure_service_item})

			inpatient_services = frappe.db.sql("""select io.name, io.parent from `tabInpatient Record` ip,
			`tabInpatient Occupancy` io where ip.patient=%s and io.parent=ip.name and
			io.left=1 and io.invoiced=0""", (patient.name))
			if inpatient_services:
				for inpatient_service in inpatient_services:
					inpatient_occupancy = frappe.get_doc("Inpatient Occupancy", inpatient_service[0])
					inpatient_record = frappe.get_doc("Inpatient Record", inpatient_service[1])
					service_unit_type = frappe.get_doc("Healthcare Service Unit Type", frappe.db.get_value("Healthcare Service Unit", inpatient_occupancy.service_unit, "service_unit_type"))
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
							service_item_rate = False
							if inpatient_record.insurance :
								service_item_rate, discount_percentage = get_insurance_deatils(inpatient_record.insurance, service_unit_type.item)
							if inpatient_record.insurance and service_item_rate:
								item_to_invoice.append({'reference_type': 'Inpatient Occupancy', 'reference_name': inpatient_occupancy.name,
								'service': service_unit_type.item, 'cost_center': cost_center, 'qty': qty, 'rate': service_item_rate, 'discount_percentage': discount_percentage})
							else:
								item_to_invoice.append({'reference_type': 'Inpatient Occupancy', 'reference_name': inpatient_occupancy.name,
								'service': service_unit_type.item, 'cost_center': cost_center, 'qty': qty})
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

	practitioner_charge = get_practitioner_charge(doc.practitioner, is_ip)

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

def get_practitioner_charge(practitioner, is_ip):
	if is_ip:
		practitioner_charge = frappe.db.get_value("Healthcare Practitioner", practitioner, "inpatient_visit_charge")
	else:
		practitioner_charge = frappe.db.get_value("Healthcare Practitioner", practitioner, "op_consulting_charge")
	if practitioner_charge:
		return practitioner_charge
	return False

def manage_invoice_submit_cancel(doc, method):
	if doc.items:
		jv_amount = {}
		for item in doc.items:
			if item.get("reference_dt") and item.get("reference_dn"):
				if frappe.get_meta(item.reference_dt).has_field("invoiced"):
					set_invoiced(item, method, doc.name)
				if frappe.get_meta(item.reference_dt).has_field("insurance"):
					manage_insurance_invoice_on_submit(item.reference_dt, item.reference_dn, jv_amount,	item.item_code)
		if jv_amount and method == "on_submit":
			for key in jv_amount:
				create_insurance_claim(frappe.get_doc("Insurance Assignment", key), jv_amount[key], doc)
	if method=="on_submit" and frappe.db.get_value("Healthcare Settings", None, "create_test_on_si_submit") == '1':
		create_multiple("Sales Invoice", doc.name)

def set_invoiced(item, method, ref_invoice=None):
	invoiced = False
	if(method=="on_submit"):
		if not item.delivery_note:
			validate_invoiced_on_submit(item)
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
		frappe.throw(_("The item referenced by {0} - {1} is already invoiced"\
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
						item_to_invoice.append({'reference_type': 'Drug Prescription', 'reference_name': drug_line.name,
						'drug_code': drug_line.drug_code, 'quantity': qty, 'description': description})
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
		price_list_name = frappe.db.get_value("Price List", {"selling": 1})
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
def get_insurance_deatils(insurance, service_item):
	healthcare_insurance = frappe.get_doc("Insurance Assignment", insurance)
	price_list = frappe.db.get_value("Insurance Contract", {'insurance_company': healthcare_insurance.insurance_company, 'is_active': 1} , "price_list")
	print(healthcare_insurance.discount)
	item_price = frappe.db.exists("Item Price",
		{
			'item_code': service_item,
			'price_list': price_list
		}
	)
	if item_price:
		app_procedure_rate= frappe.db.get_value("Item Price", item_price, 'price_list_rate')
		if app_procedure_rate and healthcare_insurance.discount and healthcare_insurance.discount >0:
			app_procedure_rate=app_procedure_rate - (app_procedure_rate*0.01*healthcare_insurance.discount)
			return app_procedure_rate,healthcare_insurance.discount
	return False, False

def manage_insurance_invoice_on_submit(reference_dt, reference_dn, jv_amount, app_service_item):
	insurance = frappe.db.get_value(reference_dt, reference_dn, 'insurance')
	if insurance:
		amount = get_insurance_deatils(insurance, app_service_item)[0]
		if amount:
			if insurance in jv_amount:
				jv_amount[insurance] += amount
			else:
				jv_amount[insurance] = amount
	return jv_amount

def create_insurance_claim(insurance, amount, doc):
	# create claim
	insurance_claim=frappe.new_doc('Insurance Claim')
	insurance_claim.patient=doc.patient
	insurance_claim.insurance_company=insurance.insurance_company
	insurance_claim.insurance_assignment=insurance.name
	insurance_claim.claim_percentage=insurance.coverage
	insurance_claim.bill_amount=amount
	insurance_claim.claim_amount=amount*0.01*insurance.coverage
	insurance_claim.created_by=frappe.session.user
	insurance_claim.created_on=nowdate()
	insurance_claim.sales_invoice=doc.name
	insurance_claim.claim_status="Draft"
	insurance_claim.save(ignore_permissions = True)
	insurance_claim.submit()
@frappe.whitelist()
def get_sales_invoice_for_healthcare_doc(doctype, docname):
	sales_item_exist = exist_invoice_item_for_healthcare_doc(doctype, docname)
	if sales_item_exist:
		return frappe.get_doc("Sales Invoice", frappe.db.get_value("Sales Invoice Item", sales_item_exist, "parent"))
	return False

def sales_item_details_for_healthcare_doc(item_code, doc, wh=None):
	price_list, price_list_currency = frappe.db.get_values("Price List", {"selling": 1}, ['name', 'currency'])[0]
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
		print(item.invoice_additional_quantity_used)
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
		if doc.invoiced:
			frappe.throw(_("Can not cancel invoiced {0}").format(doc.doctype))
