# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.utils import time_diff_in_hours, rounded, getdate, add_days,nowdate
from frappe.model.document import Document

class InsuranceClaimSubmission(Document):
	def on_submit(self):
		self.update_claim_details()
		self.create_submission_jv()
	def update_claim_details(self):
		if self.insurance_claim_submission_item:
			for item in self.insurance_claim_submission_item:
				insurance_claim= frappe.get_doc("Insurance Claim",item.insurance_claim)
				if insurance_claim:
					frappe.db.set_value("Insurance Claim", insurance_claim.name, "submitted_by", frappe.session.user)
					frappe.db.set_value("Insurance Claim", insurance_claim.name, "submitted_on", nowdate())
					frappe.db.set_value("Insurance Claim", insurance_claim.name, "claim_status", "Claim Submitted")
	def complete(self):
		if self.insurance_claim_submission_item:
			update_final_claim_details(self.insurance_claim_submission_item)
		self.is_finished=1
		self.save()

	def create_submission_jv(self):
		# create jv
		insurance_company = frappe.get_doc('Insurance Company', self.insurance_company)
		from erpnext.accounts.party import get_party_account
		journal_entry = frappe.new_doc('Journal Entry')
		journal_entry.voucher_type = 'Journal Entry'
		journal_entry.company = insurance_company.company
		journal_entry.posting_date =  nowdate()
		accounts = []
		tax_amount = 0.0
		accounts.append({
				"account": insurance_company.pre_claim_submission_account,
				"credit_in_account_currency": self.total_claim_amount,
				"party_type": "Customer",
				"party": insurance_company.customer,
			})
		accounts.append({
				"account": insurance_company.submission_claim__account,
				"debit_in_account_currency": self.total_claim_amount,
				"party_type": "Customer",
				"party": insurance_company.customer,
			})
		journal_entry.set("accounts", accounts)
		journal_entry.save(ignore_permissions = True)
		journal_entry.submit()

	def create_payment_entry(self):
		insurance_company = frappe.get_doc('Insurance Company', self.insurance_company)
		payment_entry = frappe.new_doc('Payment Entry')
		payment_entry.voucher_type = 'Payment Entry'
		payment_entry.company = insurance_company.company
		payment_entry.posting_date =  nowdate()
		payment_entry.payment_type="Receive"
		payment_entry.party_type="Customer"
		payment_entry.party = insurance_company.customer
		payment_entry.paid_amount=self.total_approved_amount
		payment_entry.setup_party_account_field()
		payment_entry.set_missing_values()
		return payment_entry.as_dict()
@frappe.whitelist()
def get_claim_submission_item(insurance_company, patient=False):
	query = """
		select
			 dn.name as insurance_claim, dn.sales_invoice, dn.patient, dn.insurance_company, dn.claim_amount, dn.claim_status
		from
			`tabInsurance Claim` dn
		where
			dn.insurance_company='{0}' and dn.docstatus=1  and dn.claim_status="Claim Created"
	"""
	if patient:
		query += """ and dn.patient=%(patient)s"""
	
	return frappe.db.sql(query.format(insurance_company),{
			'patient': patient
		}, as_dict=True)

@frappe.whitelist()
def update_final_claim_details(claims):
	from six import string_types
	if isinstance(claims, string_types):
		claims =  json.loads(claims)
	for claim in claims:
		if isinstance(claim, dict):
			claim = frappe._dict(claim)
		insurance_claim=frappe.get_doc("Insurance Claim", claim.insurance_claim)
		insurance_claim.claim_status= claim.claim_status
		if claim.approved_amount:
			insurance_claim.approved_amount=claim.approved_amount
		insurance_claim.save()
	return True

	