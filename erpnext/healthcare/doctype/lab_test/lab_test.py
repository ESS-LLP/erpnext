# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, cstr, get_link_to_form, flt, nowdate, nowtime, cstr, to_timedelta
from erpnext.healthcare.doctype.healthcare_settings.healthcare_settings import get_account
from erpnext.stock.stock_ledger import get_previous_sle
from erpnext.stock.get_item_details import get_item_details

class LabTest(Document):
	def validate(self):
		if not self.is_new():
			self.set_secondary_uom_result()
		if self.consume_stock:
			allow_start = self.set_actual_qty()
			if allow_start:
				return 'insufficient stock'
		if self.items:
			self.invoice_separately_as_consumables = False
			for item in self.items:
				if item.invoice_separately_as_consumables:
					self.invoice_separately_as_consumables = True

	def on_submit(self):
		self.validate_result_values()
		self.db_set('submitted_date', getdate())
		self.db_set('status', 'Completed')
		insert_lab_test_to_medical_record(self)
		make_insurance_claim(self)
		# consumable
		stock_entry = consumable_item_process(self)
		if stock_entry:
			frappe.msgprint(_('Stock Entry {0} created').format(stock_entry), indicator='green')

	def on_cancel(self):
		self.db_set('status', 'Cancelled')
		delete_lab_test_from_medical_record(self)
		self.reload()

	def on_update(self):
		if self.sensitivity_test_items:
			sensitivity = sorted(self.sensitivity_test_items, key=lambda x: x.antibiotic_sensitivity)
			for i, item in enumerate(sensitivity):
				item.idx = i + 1
			self.sensitivity_test_items = sensitivity

	def before_insert(self):
		if self.consume_stock:
			self.set_actual_qty()

	def after_insert(self):
		if self.healthcare_service_order:
			frappe.db.set_value('Healthcare Service Order', self.healthcare_service_order, 'status', 'Completed')
			# frappe.db.set_value('Healthcare Service Order', self.healthcare_service_order, 'lab_test', self.name)
			if frappe.db.get_value('Healthcare Service Order', self.healthcare_service_order, 'invoiced'):
				self.invoiced = True
		if not self.lab_test_name and self.template:
			self.load_test_from_template()
			self.reload()

	def load_test_from_template(self):
		lab_test = self
		create_test_from_template(lab_test)
		self.reload()

	def set_secondary_uom_result(self):
		for item in self.normal_test_items:
			if item.result_value and item.secondary_uom and item.conversion_factor:
				try:
					item.secondary_uom_result = float(item.result_value) * float(item.conversion_factor)
				except:
					item.secondary_uom_result = ''
					frappe.msgprint(_('Row #{0}: Result for Secondary UOM not calculated'.format(item.idx)), title = _('Warning'))

	def validate_result_values(self):
		if self.normal_test_items:
			for item in self.normal_test_items:
				if not item.result_value and not item.allow_blank and item.require_result_value:
					frappe.throw(_('Row #{0}: Please enter the result value for {1}').format(
						item.idx, frappe.bold(item.lab_test_name)), title=_('Mandatory Results'))

		if self.descriptive_test_items:
			for item in self.descriptive_test_items:
				if not item.result_value and not item.allow_blank and item.require_result_value:
					frappe.throw(_('Row #{0}: Please enter the result value for {1}').format(
						item.idx, frappe.bold(item.lab_test_particulars)), title=_('Mandatory Results'))

	def set_actual_qty(self):
		allow_negative_stock = frappe.db.get_single_value(
			'Stock Settings', 'allow_negative_stock')

		allow_start = True
		for d in self.get('items'):
			d.actual_qty = get_stock_qty(d.item_code, self.warehouse)
			# validate qty
			if not allow_negative_stock and d.actual_qty < d.qty:
				allow_start = False
				break
		return allow_start

def create_test_from_template(lab_test):
	template = frappe.get_doc('Lab Test Template', lab_test.template)
	patient = frappe.get_doc('Patient', lab_test.patient)

	lab_test.lab_test_name = template.lab_test_name
	lab_test.result_date = getdate()
	lab_test.department = template.department
	lab_test.lab_test_group = template.lab_test_group
	lab_test.legend_print_position = template.legend_print_position
	lab_test.result_legend = template.result_legend
	lab_test.worksheet_instructions = template.worksheet_instructions

	lab_test = create_sample_collection(lab_test, template, patient, None)
	lab_test = load_result_format(lab_test, template, None, None)

@frappe.whitelist()
def update_status(status, name):
	if name and status:
		frappe.db.set_value('Lab Test', name, {
			'status': status,
			'approved_date': getdate()
		})

@frappe.whitelist()
def create_multiple(doctype, docname):
	if not doctype or not docname:
		frappe.throw(_('Sales Invoice or Patient Encounter is required to create Lab Tests'), title=_('Insufficient Data'))

	lab_test_created = False
	if doctype == 'Sales Invoice':
		lab_test_created = create_lab_test_from_invoice(docname)
	elif doctype == 'Patient Encounter':
		lab_test_created = create_lab_test_from_encounter(docname)

	if lab_test_created:
		frappe.msgprint(_('Lab Test(s) {0} created successfully').format(lab_test_created), indicator='green')
	# else:
	# 	frappe.msgprint(_('No Lab Tests created'))

def create_lab_test_from_encounter(encounter):
	lab_test_created = False
	encounter = frappe.get_doc('Patient Encounter', encounter)
	if encounter:
		patient = frappe.get_doc('Patient', encounter.patient)
		service_orders = frappe.db.get_list('Healthcare Service Order', filters={ 'order_group': encounter.name, 'status': ['!=', 'Completed'], 'order_doctype': 'Lab Test Template'},
		fields=['name'])
		if service_orders:
			for service_order in service_orders:
				service_order_doc = frappe.get_doc('Healthcare Service Order', service_order)
				template = get_lab_test_template(service_order_doc.order)
				if template:
					lab_test = create_lab_test_doc(service_order_doc.invoiced, encounter.practitioner, patient, template, encounter.company)
					lab_test.healthcare_service_order = service_order_doc.name
					lab_test.save(ignore_permissions = True)
					frappe.db.set_value('Healthcare Service Order', service_order_doc.name, 'status', 'Completed')
					if not lab_test_created:
						lab_test_created = lab_test.name
					else:
						lab_test_created += ', ' + lab_test.name
	return lab_test_created

def create_lab_test_from_invoice(sales_invoice):
	lab_tests_created = False
	invoice = frappe.get_doc('Sales Invoice', sales_invoice)
	if invoice and invoice.patient:
		patient = frappe.get_doc('Patient', invoice.patient)
		for item in invoice.items:
			lab_test_created = 0
			if item.reference_dt == 'Lab Prescription':
				lab_test_created = frappe.db.get_value('Lab Prescription', item.reference_dn, 'lab_test_created')
			elif item.reference_dt == 'Lab Test':
				lab_test_created = 1
			if lab_test_created != 1:
				template = get_lab_test_template(item.item_code)
				if template:
					lab_test = create_lab_test_doc(True, invoice.ref_practitioner, patient, template, invoice.company)
					if item.reference_dt == 'Lab Prescription':
						lab_test.prescription = item.reference_dn
					lab_test.save(ignore_permissions = True)
					if item.reference_dt != 'Lab Prescription':
						frappe.db.set_value('Sales Invoice Item', item.name, 'reference_dt', 'Lab Test')
						frappe.db.set_value('Sales Invoice Item', item.name, 'reference_dn', lab_test.name)
					if not lab_tests_created:
						lab_tests_created = lab_test.name
					else:
						lab_tests_created += ', ' + lab_test.name
	return lab_tests_created

def get_lab_test_template(item):
	template_id = frappe.db.exists('Lab Test Template', {'item': item})
	if template_id:
		return frappe.get_doc('Lab Test Template', template_id)
	return False

def create_lab_test_doc(invoiced, practitioner, patient, template, company):
	lab_test = frappe.new_doc('Lab Test')
	lab_test.invoiced = invoiced
	lab_test.practitioner = practitioner
	lab_test.patient = patient.name
	lab_test.patient_age = patient.get_age()
	lab_test.patient_sex = patient.sex
	lab_test.email = patient.email
	lab_test.mobile = patient.mobile
	lab_test.report_preference = patient.report_preference
	lab_test.department = template.department
	lab_test.template = template.name
	lab_test.lab_test_group = template.lab_test_group
	lab_test.result_date = getdate()
	lab_test.company = company
	return lab_test

def create_normals(template, lab_test):
	lab_test.normal_toggle = 1
	normal = lab_test.append('normal_test_items')
	normal.lab_test_name = template.lab_test_name
	normal.lab_test_uom = template.lab_test_uom
	normal.secondary_uom = template.secondary_uom
	normal.conversion_factor = template.conversion_factor
	normal.normal_range = template.lab_test_normal_range
	normal.require_result_value = 1
	normal.allow_blank = 0
	normal.template = template.name

def create_compounds(template, lab_test, is_group):
	lab_test.normal_toggle = 1
	for normal_test_template in template.normal_test_templates:
		normal = lab_test.append('normal_test_items')
		if is_group:
			normal.lab_test_event = normal_test_template.lab_test_event
		else:
			normal.lab_test_name = normal_test_template.lab_test_event

		normal.lab_test_uom = normal_test_template.lab_test_uom
		normal.secondary_uom = normal_test_template.secondary_uom
		normal.conversion_factor = normal_test_template.conversion_factor
		normal.normal_range = normal_test_template.normal_range
		normal.require_result_value = 1
		normal.allow_blank = normal_test_template.allow_blank
		normal.template = template.name

def create_descriptives(template, lab_test):
	lab_test.descriptive_toggle = 1
	if template.sensitivity:
		lab_test.sensitivity_toggle = 1
	for descriptive_test_template in template.descriptive_test_templates:
		descriptive = lab_test.append('descriptive_test_items')
		descriptive.lab_test_particulars = descriptive_test_template.particulars
		descriptive.require_result_value = 1
		descriptive.allow_blank = descriptive_test_template.allow_blank
		descriptive.template = template.name

def create_sample_doc(template, patient, invoice, company = None):
	if template.sample:
		sample_exists = frappe.db.exists({
			'doctype': 'Sample Collection',
			'patient': patient.name,
			'docstatus': 0,
			'sample': template.sample
		})

		if sample_exists:
			# update sample collection by adding quantity
			sample_collection = frappe.get_doc('Sample Collection', sample_exists[0][0])
			quantity = int(sample_collection.sample_qty) + int(template.sample_qty)
			if template.sample_details:
				sample_details = sample_collection.sample_details + '\n-\n' + _('Test: ')
				sample_details += (template.get('lab_test_name') or template.get('template')) +	'\n'
				sample_details += _('Collection Details: ') + '\n\t' + template.sample_details
				frappe.db.set_value('Sample Collection', sample_collection.name, 'sample_details', sample_details)

			frappe.db.set_value('Sample Collection', sample_collection.name, 'sample_qty', quantity)

		else:
			# Create Sample Collection for template, copy vals from Invoice
			sample_collection = frappe.new_doc('Sample Collection')
			if invoice:
				sample_collection.invoiced = True

			sample_collection.patient = patient.name
			sample_collection.patient_age = patient.get_age()
			sample_collection.patient_sex = patient.sex
			sample_collection.sample = template.sample
			sample_collection.sample_uom = template.sample_uom
			sample_collection.sample_qty = template.sample_qty
			sample_collection.company = company

			if template.sample_details:
				sample_collection.sample_details = _('Test :') + (template.get('lab_test_name') or template.get('template')) + '\n' + 'Collection Detials:\n\t' + template.sample_details
			sample_collection.save(ignore_permissions=True)

		return sample_collection

def create_sample_collection(lab_test, template, patient, invoice):
	if frappe.get_cached_value('Healthcare Settings', None, 'create_sample_collection_for_lab_test'):
		sample_collection = create_sample_doc(template, patient, invoice, lab_test.company)
		if sample_collection:
			lab_test.sample = sample_collection.name
			sample_collection_doc = get_link_to_form('Sample Collection', sample_collection.name)
			frappe.msgprint(_('Sample Collection {0} has been created').format(sample_collection_doc),
				title=_('Sample Collection'), indicator='green')
	return lab_test

def load_result_format(lab_test, template, prescription, invoice):
	if template.lab_test_template_type == 'Single':
		create_normals(template, lab_test)

	elif template.lab_test_template_type == 'Compound':
		create_compounds(template, lab_test, False)

	elif template.lab_test_template_type == 'Descriptive':
		create_descriptives(template, lab_test)

	elif template.lab_test_template_type == 'Grouped':
		# Iterate for each template in the group and create one result for all.
		for lab_test_group in template.lab_test_groups:
			# Template_in_group = None
			if lab_test_group.lab_test_template:
				template_in_group = frappe.get_doc('Lab Test Template', lab_test_group.lab_test_template)
				if template_in_group:
					if template_in_group.lab_test_template_type == 'Single':
						create_normals(template_in_group, lab_test)

					elif template_in_group.lab_test_template_type == 'Compound':
						normal_heading = lab_test.append('normal_test_items')
						normal_heading.lab_test_name = template_in_group.lab_test_name
						normal_heading.require_result_value = 0
						normal_heading.allow_blank = 1
						normal_heading.template = template_in_group.name
						create_compounds(template_in_group, lab_test, True)

					elif template_in_group.lab_test_template_type == 'Descriptive':
						descriptive_heading = lab_test.append('descriptive_test_items')
						descriptive_heading.lab_test_name = template_in_group.lab_test_name
						descriptive_heading.require_result_value = 0
						descriptive_heading.allow_blank = 1
						descriptive_heading.template = template_in_group.name
						create_descriptives(template_in_group, lab_test)

			else: # Lab Test Group - Add New Line
				normal = lab_test.append('normal_test_items')
				normal.lab_test_name = lab_test_group.group_event
				normal.lab_test_uom = lab_test_group.group_test_uom
				normal.secondary_uom = lab_test_group.secondary_uom
				normal.conversion_factor = lab_test_group.conversion_factor
				normal.normal_range = lab_test_group.group_test_normal_range
				normal.allow_blank = lab_test_group.allow_blank
				normal.require_result_value = 1
				normal.template = template.name

	if template.lab_test_template_type != 'No Result':
		if prescription:
			lab_test.prescription = prescription
			if invoice:
				frappe.db.set_value('Lab Prescription', prescription, 'invoiced', True)
				frappe.db.set_value('Healthcare Service Order', lab_test.healthcare_service_order, 'status', 'Completed')
		lab_test.save(ignore_permissions=True) # Insert the result
		return lab_test

@frappe.whitelist()
def get_employee_by_user_id(user_id):
	emp_id = frappe.db.exists('Employee', { 'user_id': user_id })
	if emp_id:
		return frappe.get_doc('Employee', emp_id)
	return None

def insert_lab_test_to_medical_record(doc):
	table_row = False
	subject = cstr(doc.lab_test_name)
	if doc.practitioner:
		subject += frappe.bold(_('Healthcare Practitioner: '))+ doc.practitioner + '<br>'
	if doc.normal_test_items:
		item = doc.normal_test_items[0]
		comment = ''
		if item.lab_test_comment:
			comment = str(item.lab_test_comment)
		table_row = frappe.bold(_('Lab Test Conducted: ')) + item.lab_test_name

		if item.lab_test_event:
			table_row += frappe.bold(_('Lab Test Event: ')) + item.lab_test_event

		if item.result_value:
			table_row += ' ' + frappe.bold(_('Lab Test Result: ')) + item.result_value

		if item.normal_range:
			table_row += ' ' + _('Normal Range: ') + item.normal_range
		table_row += ' ' + comment

	elif doc.descriptive_test_items:
		item = doc.descriptive_test_items[0]

		if item.lab_test_particulars and item.result_value:
			table_row = item.lab_test_particulars + ' ' + item.result_value

	elif doc.sensitivity_test_items:
		item = doc.sensitivity_test_items[0]

		if item.antibiotic and item.antibiotic_sensitivity:
			table_row = item.antibiotic + ' ' + item.antibiotic_sensitivity

	if table_row:
		subject += '<br>' + table_row
	if doc.lab_test_comment:
		subject += '<br>' + cstr(doc.lab_test_comment)

	medical_record = frappe.new_doc('Patient Medical Record')
	medical_record.patient = doc.patient
	medical_record.subject = subject
	medical_record.status = 'Open'
	medical_record.communication_date = doc.result_date
	medical_record.reference_doctype = 'Lab Test'
	medical_record.reference_name = doc.name
	medical_record.reference_owner = doc.owner
	medical_record.save(ignore_permissions = True)

def delete_lab_test_from_medical_record(self):
	medical_record_id = frappe.db.sql('select name from `tabPatient Medical Record` where reference_name=%s', (self.name))

	if medical_record_id and medical_record_id[0][0]:
		frappe.delete_doc('Patient Medical Record', medical_record_id[0][0])

@frappe.whitelist()
def get_lab_test_prescribed(patient):
	return frappe.db.sql(
			'''
			select
				hso.order as lab_test_code,
				hso.order_group,
				hso.invoiced,
				hso.ordered_by as practitioner,
				hso.order_date as encounter_date,
				hso.source,
				hso.referring_practitioner,
				hso.name,
				hso.insurance_subscription,
				hso.insurance_company
			from
				`tabHealthcare Service Order` hso
			where
				hso.patient=%s
				and hso.status!=%s
				and hso.order_doctype=%s
		''', (patient, 'Completed', 'Lab Test Template'))

def make_insurance_claim(doc):
	if doc.insurance_subscription and not doc.insurance_claim:
		from erpnext.healthcare.utils import create_insurance_claim
		billing_item = frappe.get_cached_value('Lab Test Template', doc.template, 'item')
		insurance_claim, claim_status = create_insurance_claim(doc, 'Lab Test Template', doc.template, 1, billing_item)
		if insurance_claim:
			frappe.set_value(doc.doctype, doc.name ,'insurance_claim', insurance_claim)
			frappe.set_value(doc.doctype, doc.name ,'claim_status', claim_status)
			doc.reload()

def consumable_item_process(doc):
	if doc.consume_stock and doc.items:
		stock_entry = make_stock_entry(doc)

	if doc.items:
		consumable_total_amount = 0
		consumption_details = False
		customer = frappe.db.get_value('Patient', doc.patient, 'customer')
		if customer:
			for item in doc.items:
				if item.invoice_separately_as_consumables:
					price_list, price_list_currency = frappe.db.get_values(
						'Price List', {'selling': 1}, ['name', 'currency'])[0]
					args = {
						'doctype': 'Sales Invoice',
						'item_code': item.item_code,
						'company': doc.company,
						'warehouse': doc.warehouse,
						'customer': customer,
						'selling_price_list': price_list,
						'price_list_currency': price_list_currency,
						'plc_conversion_rate': 1.0,
						'conversion_rate': 1.0
					}
					item_details = get_item_details(args)
					item_price = item_details.price_list_rate * item.qty
					item_consumption_details = item_details.item_name + ' ' + \
						str(item.qty) + ' ' + item.uom + \
						' ' + str(item_price)
					consumable_total_amount += item_price
					if not consumption_details:
						consumption_details = _(
							'Lab Test ({0}):').format(doc.name)
					consumption_details += '\n\t' + item_consumption_details

			if consumable_total_amount > 0:
				frappe.db.set_value(
					'Lab Test', doc.name, 'consumable_total_amount', consumable_total_amount)
				frappe.db.set_value(
					'Lab Test', doc.name, 'consumption_details', consumption_details)
		else:
			frappe.throw(_('Please set Customer in Patient {0}').format(
				frappe.bold(doc.patient)), title=_('Customer Not Found'))
	if doc.consume_stock and doc.items:
		return stock_entry

@frappe.whitelist()
def make_stock_entry(doc):
    stock_entry = frappe.new_doc('Stock Entry')
    stock_entry = set_stock_items(stock_entry, doc.name, 'Lab Test')
    stock_entry.stock_entry_type = 'Material Issue'
    stock_entry.from_warehouse = doc.warehouse
    stock_entry.company = doc.company
    expense_account = get_account(
        None, 'expense_account', 'Healthcare Settings', doc.company)

    for item_line in stock_entry.items:
        cost_center = frappe.get_cached_value(
            'Company',  doc.company,  'cost_center')
        item_line.cost_center = cost_center
        item_line.expense_account = expense_account

    stock_entry.save(ignore_permissions=True)
    stock_entry.submit()
    return stock_entry.name

@frappe.whitelist()
def get_procedure_consumables(template):
    return get_items('Clinical Procedure Item', template, 'Lab Test Template')

@frappe.whitelist()
def set_stock_items(doc, stock_detail_parent, parenttype):
    items = get_items('Clinical Procedure Item',
                      stock_detail_parent, parenttype)

    for item in items:
        se_child = doc.append('items')
        se_child.item_code = item.item_code
        se_child.item_name = item.item_name
        se_child.uom = item.uom
        se_child.stock_uom = item.stock_uom
        se_child.qty = flt(item.qty)
        # in stock uom
        se_child.transfer_qty = flt(item.transfer_qty)
        se_child.conversion_factor = flt(item.conversion_factor)
        if item.batch_no:
            se_child.batch_no = item.batch_no
        if parenttype == 'Lab Test Template':
            se_child.invoice_separately_as_consumables = item.invoice_separately_as_consumables

    return doc

def get_items(table, parent, parenttype):
    items = frappe.db.get_all(table, filters={
        'parent': parent,
        'parenttype': parenttype
    }, fields=['*'])

    return items

def get_stock_qty(item_code, warehouse):
    return get_previous_sle({
        'item_code': item_code,
        'warehouse': warehouse,
        'posting_date': nowdate(),
        'posting_time': nowtime()
    }).get('qty_after_transaction') or 0