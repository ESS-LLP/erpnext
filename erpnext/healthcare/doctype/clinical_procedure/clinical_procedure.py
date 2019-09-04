# -*- coding: utf-8 -*-
# Copyright (c) 2017, ESS LLP and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, nowdate, nowtime, cstr, to_timedelta, getdate
from erpnext.healthcare.doctype.healthcare_settings.healthcare_settings import get_account, get_receivable_account
from erpnext.healthcare.doctype.lab_test.lab_test import create_sample_doc, create_lab_test_doc
from erpnext.stock.stock_ledger import get_previous_sle
import datetime
from erpnext.healthcare.utils import sales_item_details_for_healthcare_doc, get_procedure_delivery_item, item_reduce_procedure_rate, manage_healthcare_doc_cancel, get_insurance_details

class ClinicalProcedure(Document):
	def validate(self):
		if self.consume_stock and not self.status == 'Draft':
			if not self.warehouse:
				frappe.throw(_("Set warehouse for Procedure {0} ").format(self.name))
			self.set_actual_qty()

	def before_insert(self):
		if self.consume_stock:
			set_stock_items(self, self.procedure_template, "Clinical Procedure Template")
			self.set_actual_qty();
		set_procedure_pre_post_tasks(self)

	def after_insert(self):
		if self.prescription:
			frappe.db.set_value("Procedure Prescription", self.prescription, "procedure_created", 1)
			ip_record_procdure = frappe.db.exists(
				"Inpatient Record Procedure",
				{"prescription": self.prescription}
			)
			if ip_record_procdure:
				frappe.db.set_value("Inpatient Record Procedure", ip_record_procdure, "procedure_created", 1)
		if self.inpatient_record_procedure:
			frappe.db.set_value("Inpatient Record Procedure", self.inpatient_record_procedure, "procedure_created", 1)
		if self.appointment and self.docstatus==0:
			frappe.db.set_value("Patient Appointment", self.appointment, "status", "In Progress")
		template = frappe.get_doc("Clinical Procedure Template", self.procedure_template)
		if template.sample:
			patient = frappe.get_doc("Patient", self.patient)
			sample_collection = create_sample_doc(template, patient, None)
			frappe.db.set_value("Clinical Procedure", self.name, "sample", sample_collection.name)
		create_pre_post_document(self)
		self.reload()

	def complete(self):
		if self.consume_stock and self.items:
			create_delivery_note(self)

		self.status = "Completed"

		if self.inpatient_record and frappe.db.get_value("Healthcare Settings", None, "auto_invoice_inpatient") == '1':
			self.invoice()
		self.save()

	def invoice(self):
		if not self.invoiced and self.status == "Completed" and not self.appointment:
			return invoice_clinical_procedure(self)
		return False

	def start(self):
		allow_start = self.set_actual_qty()
		if allow_start:
			self.status = 'In Progress'
			insert_clinical_procedure_to_medical_record(self)
			frappe.db.set_value("Patient Appointment", self.appointment, "status", "Closed")
		else:
			self.status = 'Draft'
		self.save()

	def set_actual_qty(self):
		allow_negative_stock = cint(frappe.db.get_value("Stock Settings", None, "allow_negative_stock"))

		allow_start = True
		for d in self.get('items'):
			d.actual_qty = get_stock_qty(d.item_code, self.warehouse)
			# validate qty
			if not allow_negative_stock and d.actual_qty < d.qty:
				allow_start = False

		return allow_start

	def make_material_transfer(self):
		stock_entry = frappe.new_doc("Stock Entry")

		stock_entry.purpose = "Material Transfer"
		stock_entry.to_warehouse = self.warehouse
		expense_account = get_account(None, "expense_account", "Healthcare Settings", self.company)
		for item in self.items:
			if item.qty > item.actual_qty:
				se_child = stock_entry.append('items')
				se_child.item_code = item.item_code
				se_child.item_name = item.item_name
				se_child.uom = item.uom
				se_child.stock_uom = item.stock_uom
				se_child.qty = flt(item.qty-item.actual_qty)
				se_child.t_warehouse = self.warehouse
				# in stock uom
				se_child.transfer_qty = flt(item.transfer_qty)
				se_child.conversion_factor = flt(item.conversion_factor)
				cost_center = frappe.get_cached_value('Company',  self.company,  'cost_center')
				se_child.cost_center = cost_center
				se_child.expense_account = expense_account
		return stock_entry.as_dict()

	def on_trash(self):
		if self.prescription:
			frappe.db.set_value("Procedure Prescription", self.prescription, "procedure_created", 0)

	def on_cancel(self):
		manage_healthcare_doc_cancel(self)

def set_procedure_pre_post_tasks(doc):
	if doc.procedure_template:
		template = frappe.get_doc("Clinical Procedure Template", doc.procedure_template)
		if template.nursing_tasks:
			for nursing_task in template.nursing_tasks:
				nursing_task_item = doc.append("nursing_tasks")
				nursing_task_item.check_list = nursing_task.check_list
				nursing_task_item.task = nursing_task.task
				nursing_task_item.expected_time = nursing_task.expected_time

		if template.investigations:
			for investigation in template.investigations:
				investigation_item = doc.append("investigations")
				investigation_item.lab_test = investigation.lab_test
				investigation_item.task = investigation.task
				investigation_item.expected_time = investigation.expected_time

	return doc

def create_pre_post_document(doc):
	if doc.nursing_tasks:
		for nursing_task in doc.nursing_tasks:
			if not nursing_task.nursing_task_reference:
				create_nursing_task(doc, nursing_task)

	if doc.investigations:
		for investigation in doc.investigations:
			if not investigation.lab_test_reference:
				lab_test = create_lab_test_doc(True, doc.practitioner, frappe.get_doc("Patient", doc.patient), frappe.get_doc("Lab Test Template", investigation.lab_test))
				lab_test.reference_dt = doc.doctype
				lab_test.reference_dn = doc.name
				lab_test.expected_result_date = doc.start_date
				if doc.start_time and investigation.expected_time and investigation.expected_time > 0:
					if investigation.task == "After":
						lab_test.expected_result_time = to_timedelta(doc.start_time) + datetime.timedelta(seconds=investigation.expected_time*60)
					elif investigation.task == "Before":
						lab_test.expected_result_time = to_timedelta(doc.start_time) - datetime.timedelta(seconds=investigation.expected_time*60)
				lab_test.save(ignore_permissions = True)
				# frappe.db.set_value("Clinical Procedure Lab Test", investigation.name, "lab_test_reference", lab_test.name)

def create_nursing_task(doc, nursing_task):
	hc_nursing_task = frappe.new_doc("Healthcare Nursing Task")
	hc_nursing_task.patient = doc.patient
	hc_nursing_task.practitioner = doc.practitioner
	hc_nursing_task.task = nursing_task.check_list
	hc_nursing_task.service_unit = doc.service_unit
	hc_nursing_task.medical_department = doc.medical_department
	hc_nursing_task.task_order = nursing_task.task
	hc_nursing_task.reference_doctype = doc.doctype
	hc_nursing_task.reference_docname = doc.name
	hc_nursing_task.date = doc.start_date
	if doc.start_time and nursing_task.expected_time and nursing_task.expected_time > 0:
		if nursing_task.task == "After":
			hc_nursing_task.time = to_timedelta(doc.start_time) + datetime.timedelta(seconds=nursing_task.expected_time*60)
		elif nursing_task.task == "Before":
			hc_nursing_task.time = to_timedelta(doc.start_time) - datetime.timedelta(seconds=nursing_task.expected_time*60)
	hc_nursing_task.save(ignore_permissions=True)
	# frappe.db.set_value("Clinical Procedure Nursing Task", nursing_task.name, "nursing_task_reference", nursing_task.name)


@frappe.whitelist()
def get_stock_qty(item_code, warehouse):
	return get_previous_sle({
		"item_code": item_code,
		"warehouse": warehouse,
		"posting_date": nowdate(),
		"posting_time": nowtime()
	}).get("qty_after_transaction") or 0

@frappe.whitelist()
def set_stock_items(doc, stock_detail_parent, parenttype):
	item_dict = get_item_dict("Clinical Procedure Item", stock_detail_parent, parenttype)

	for d in item_dict:
		se_child = doc.append('items')
		se_child.item_code = d["item_code"]
		se_child.item_name = d["item_name"]
		se_child.uom = d["uom"]
		se_child.stock_uom = d["stock_uom"]
		se_child.qty = flt(d["qty"])
		# in stock uom
		se_child.transfer_qty = flt(d["transfer_qty"])
		se_child.conversion_factor = flt(d["conversion_factor"])
		if d["batch_no"]:
			se_child.batch_no = d["batch_no"]
		if parenttype == "Clinical Procedure Template" and doc.doctype == "Clinical Procedure":
			se_child.invoice_additional_quantity_used = d["invoice_additional_quantity_used"]
			se_child.procedure_qty = flt(d["qty"])
	return doc

def get_item_dict(table, parent, parenttype):
	query = """select * from `tab{table}` where parent = '{parent}' and parenttype = '{parenttype}' """

	return frappe.db.sql(query.format(table=table, parent=parent, parenttype=parenttype), as_dict=True)

def create_stock_entry(doc):
	stock_entry = frappe.new_doc("Stock Entry")
	stock_entry = set_stock_items(stock_entry, doc.name, "Clinical Procedure")
	stock_entry.purpose = "Material Issue"
	stock_entry.from_warehouse = doc.warehouse
	stock_entry.company = doc.company
	expense_account = get_account(None, "expense_account", "Healthcare Settings", doc.company)

	for item_line in stock_entry.items:
		cost_center = frappe.get_cached_value('Company',  doc.company,  'cost_center')
		#item_line.s_warehouse = warehouse #deaful source warehouse set, stock entry to copy to lines
		item_line.cost_center = cost_center
		#if not expense_account:
		#	expense_account = frappe.db.get_value("Item", item_line.item_code, "expense_account")
		item_line.expense_account = expense_account

	stock_entry.insert(ignore_permissions = True)
	stock_entry.submit()

def create_delivery_note(doc):
	delivery_note = frappe.new_doc("Delivery Note")
	delivery_note.company = doc.company
	delivery_note.patient = doc.patient
	delivery_note.patient_name = frappe.db.get_value("Patient", doc.patient, "patient_name")
	delivery_note.customer = frappe.db.get_value("Patient", doc.patient, "customer")
	delivery_note.inpatient_record = frappe.db.get_value("Patient", doc.patient, "inpatient_record")
	delivery_note.set_warehouse = doc.warehouse
	expense_account = get_account(None, "expense_account", "Healthcare Settings", doc.company)
	for item in doc.items:
		child = delivery_note.append('items')
		item_details = sales_item_details_for_healthcare_doc(item.item_code, doc)
		child.item_code = item.item_code
		child.item_name = item.item_name
		child.uom = item.uom
		child.stock_uom = item.stock_uom
		child.qty = flt(item.qty)
		child.warehouse = doc.warehouse
		cost_center = frappe.get_cached_value('Company',  doc.company,  'cost_center')
		child.cost_center = cost_center
		# if not expense_account:
		# 	expense_account = frappe.db.get_value("Item", item_line.item_code, "expense_account")
		child.expense_account = expense_account
		child.description = frappe.db.get_value("Item", item.item_code, "description")
		child.rate = item_details.price_list_rate
		child.price_list_rate = item_details.price_list_rate
		child.amount = item_details.price_list_rate * child.qty
		child.reference_dt = "Clinical Procedure"
		child.reference_dn = doc.name

	if delivery_note.items:
		delivery_note.insert(ignore_permissions = True)
		delivery_note.submit()

@frappe.whitelist()
def create_procedure(appointment):
	appointment = frappe.get_doc("Patient Appointment",appointment)
	procedure = frappe.new_doc("Clinical Procedure")
	procedure.appointment = appointment.name
	procedure.patient = appointment.patient
	procedure.patient_age = appointment.patient_age
	procedure.patient_sex = appointment.patient_sex
	procedure.procedure_template = appointment.procedure_template
	procedure.prescription = appointment.procedure_prescription
	procedure.practitioner = appointment.practitioner
	procedure.invoiced = appointment.invoiced
	procedure.medical_department = appointment.department
	procedure.start_date = appointment.appointment_date
	procedure.start_time = appointment.appointment_time
	procedure.notes = appointment.notes
	procedure.service_unit = appointment.service_unit
	procedure.company = appointment.company
	consume_stock = frappe.db.get_value("Clinical Procedure Template", appointment.procedure_template, "consume_stock")
	if consume_stock == 1:
		procedure.consume_stock = True
		warehouse = False
		if appointment.service_unit:
			warehouse = frappe.db.get_value("Healthcare Service Unit", appointment.service_unit, "warehouse")
		if not warehouse:
			warehouse = frappe.db.get_value("Stock Settings", None, "default_warehouse")
		if warehouse:
			procedure.warehouse = warehouse
	return procedure.as_dict()

def insert_clinical_procedure_to_medical_record(doc):
	subject = cstr(doc.procedure_template)
	if doc.practitioner:
		subject += " "+doc.practitioner
	if subject and doc.notes:
		subject += "<br/>"+doc.notes

	medical_record = frappe.new_doc("Patient Medical Record")
	medical_record.patient = doc.patient
	medical_record.subject = subject
	medical_record.status = "Open"
	medical_record.communication_date = doc.start_date
	medical_record.reference_doctype = "Clinical Procedure"
	medical_record.reference_name = doc.name
	medical_record.reference_owner = doc.owner
	medical_record.save(ignore_permissions=True)

def invoice_clinical_procedure(procedure):
	sales_invoice = frappe.new_doc("Sales Invoice")
	sales_invoice.patient = procedure.patient
	sales_invoice.patient_name = frappe.db.get_value("Patient", procedure.patient, "patient_name")
	sales_invoice.customer = frappe.db.get_value("Patient", procedure.patient, "customer")
	sales_invoice.appointment = procedure.appointment
	sales_invoice.inpatient_record = procedure.inpatient_record
	if procedure.appointment:
		sales_invoice.ref_practitioner = frappe.db.get_value("Patient Appointment", procedure.appointment, "ferring_practitioner")
	sales_invoice.due_date = getdate()
	sales_invoice.company = procedure.company
	sales_invoice.debit_to = get_receivable_account(procedure.company, procedure.patient)

	reduce_from_procedure_rate = 0
	cost_center = False
	if procedure.service_unit:
		cost_center = frappe.db.get_value("Healthcare Service Unit", procedure.service_unit, "cost_center")
	if procedure.consume_stock:
		delivery_note_items = get_procedure_delivery_item(procedure.patient, procedure.name)
		if delivery_note_items:
			for delivery_note_item in delivery_note_items:
				dn_item = frappe.get_doc("Delivery Note Item", delivery_note_item[0])
				reduce_from_procedure_rate += item_reduce_procedure_rate(dn_item, procedure.items)
				item_line = sales_invoice.append("items")
				item_line.item_code = dn_item.item_code
				item_details = sales_item_details_for_healthcare_doc(item_line.item_code, procedure)
				item_line.item_name = item_details.item_name
				item_line.description = frappe.db.get_value("Item", item_line.item_code, "description")
				item_line.rate = dn_item.rate
				item_line.qty = dn_item.qty
				item_line.amount = item_line.rate*item_line.qty
				item_line.reference_dt = dn_item.reference_dt
				item_line.reference_dn = dn_item.reference_dn
				item_line.cost_center = cost_center if cost_center else ''
				item_line.delivery_note = delivery_note_item[1] if delivery_note_item[1] else ''

	item_line = sales_invoice.append("items")
	item_line.item_code = frappe.db.get_value("Clinical Procedure Template", procedure.procedure_template, "item")
	item_details = sales_item_details_for_healthcare_doc(item_line.item_code, procedure)
	item_line.item_name = item_details.item_name
	item_line.description = frappe.db.get_value("Item", item_line.item_code, "description")
	item_line.rate = float(procedure.standard_selling_rate) - reduce_from_procedure_rate
	if procedure.insurance and item_line.item_code:
		insurance_details = get_insurance_details(procedure.insurance, item_line.item_code)
		if insurance_details:
			item_line.discount_percentage = insurance_details.discount
			if insurance_details.rate and insurance_details.rate > 0:
				item_line.rate = insurance_details.rate - reduce_from_procedure_rate
			item_line.rate = item_line.rate - (item_line.rate*0.01*item_line.discount_percentage)
			item_line.insurance_claim_coverage = insurance_details.coverage
	item_line.qty = 1
	item_line.amount = item_line.rate*item_line.qty
	item_line.cost_center = cost_center if cost_center else ''
	if procedure.appointment:
		item_line.reference_dt = "Patient Appointment"
		item_line.reference_dn = procedure.appointment
	else:
		item_line.reference_dt = "Clinical Procedure"
		item_line.reference_dn = procedure.name
	if procedure.insurance and item_line.insurance_claim_coverage and float(item_line.insurance_claim_coverage) > 0:
		item_line.insurance_claim_amount = item_line.amount*0.01*float(item_line.insurance_claim_coverage)
		sales_invoice.total_insurance_claim_amount = item_line.insurance_claim_amount

	sales_invoice.set_missing_values(for_validate = True)

	sales_invoice.save(ignore_permissions=True)
	return sales_invoice if sales_invoice else False

@frappe.whitelist()
def create_multiple(docname):
	procedure_created = False
	procedure_created = create_clinical_procedure(docname)
	if procedure_created:
		frappe.msgprint(_("Procedure(s) "+procedure_created+" created."))
	return procedure_created

def create_clinical_procedure(encounter_id):
	procedure_created = False
	encounter = frappe.get_doc("Patient Encounter", encounter_id)
	clinical_procedure_ids = frappe.db.sql("""select lp.name, lp.procedure, lp.invoiced
		from `tabPatient Encounter` et, `tabProcedure Prescription` lp
		where et.patient=%s and lp.parent=%s and
		lp.parent=et.name and lp.procedure_created=0 and et.docstatus<2""", (encounter.patient, encounter_id))
	if clinical_procedure_ids:
		patient = frappe.get_doc("Patient", encounter.patient)
		for clinical_procedure_id in clinical_procedure_ids:
			template = get_clinical_procedure_template(clinical_procedure_id[1])
			if template:
				clinical_procedure = create_clinical_procedure_doc(clinical_procedure_id[2], encounter.practitioner, patient, template, encounter.source, clinical_procedure_id[0], encounter.referring_practitioner)
				clinical_procedure.save(ignore_permissions = True)
				frappe.db.set_value("Procedure Prescription", clinical_procedure_id[0], "procedure_created", 1)
				if not procedure_created:
					procedure_created = clinical_procedure.name
				else:
					procedure_created += ", "+clinical_procedure.name
	return procedure_created

def get_clinical_procedure_template(item):
	template_id = check_template_exists(item)
	if template_id:
		return frappe.get_doc("Clinical Procedure Template", template_id)
	return False

def check_template_exists(item):
	template_exists = frappe.db.exists(
		"Clinical Procedure Template",
		{
			'item': item
		}
	)
	if template_exists:
		return template_exists
	return False


def create_clinical_procedure_doc(invoiced, practitioner, patient, template, source=None, prescription=None, ref_practitioner=None):
	clinical_procedure = frappe.new_doc("Clinical Procedure")
	clinical_procedure.invoiced = invoiced
	clinical_procedure.practitioner = practitioner
	clinical_procedure.patient = patient.name
	clinical_procedure.patient_age = patient.get_age()
	clinical_procedure.patient_sex = patient.sex
	clinical_procedure.prescription = prescription
	clinical_procedure.medical_department = template.medical_department
	clinical_procedure.procedure_template = template.name
	clinical_procedure.source = source
	clinical_procedure.referring_practitioner = ref_practitioner
	return clinical_procedure

@frappe.whitelist()
def create_procedure_from_encounter(patient_encounter, procedure_template, prescription):
	encounter = frappe.get_doc("Patient Encounter", patient_encounter)
	patient = encounter.patient
	procedure = create_clinical_procedure_doc(False, encounter.practitioner, frappe.get_doc("Patient", patient),
		frappe.get_doc("Clinical Procedure Template", procedure_template), source=encounter.source, ref_practitioner=encounter.referring_practitioner)
	procedure.prescription = prescription
	procedure.save(ignore_permissions = True)
	return procedure.as_dict()


@frappe.whitelist()
def get_inpatient_procedure_prescribed(patient):
	return frappe.db.sql("""select pp.name, pp.procedure, pp.parent, pp.practitioner,pp.secondary_practitioner,
	ct.source, ct.referring_practitioner, pp.prescription, ct.insurance
	from `tabInpatient Record` ct, `tabInpatient Record Procedure` pp
	where ct.patient='{0}' and pp.parent=ct.name and pp.procedure_created=0
	order by ct.creation desc""".format(patient))

@frappe.whitelist()
def get_procedure_prescribed(patient, encounter=False):
	query = """
		select
			pp.name, pp.procedure, pp.parent, ct.practitioner,
			ct.encounter_date, pp.practitioner, pp.date, pp.department, ct.source, ct.referring_practitioner, ct.insurance
		from
			`tabPatient Encounter` ct, `tabProcedure Prescription` pp
		where
			ct.patient='{0}' and pp.procedure_created=0 and pp.parent=ct.name"""

	if encounter:
		query += """ and pp.parent=%(encounter)s"""

	query += """ order by ct.creation desc"""

	return frappe.db.sql(query.format(patient),{
		'encounter': encounter
	})
