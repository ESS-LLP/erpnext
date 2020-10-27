# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class HealthcareInsurancePaymentRequest(Document):
	pass

@frappe.whitelist()
def get_claim_item(insurance_company, from_date=False, to_date=False, posting_date_type = ''):
	query = """
		select
			name, patient, healthcare_service_type, service_template, sales_invoice, discount, coverage, coverage_amount
		from
			`tabHealthcare Insurance Claim`
		where
			insurance_company='{0}' and docstatus=1  and claim_status="Approved"
	"""
	if posting_date_type == 'Claim Posting Date':
		if from_date:
			query += """ and claim_posting_date >=%(from_date)s"""
		if to_date:
			query += """ and claim_posting_date <=%(to_date)s"""
	else:
		if from_date:
			query += """ and sales_invoice_posting_date >=%(from_date)s"""
		if to_date:
			query += """ and sales_invoice_posting_date <=%(to_date)s"""

	claim_list = frappe.db.sql(query.format(insurance_company),{
			'from_date': from_date, 'to_date':to_date
		}, as_dict=True)
	if claim_list:
		return claim_list
	return False
