# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe import _, msgprint, throw
from frappe.utils import time_diff_in_hours, rounded, getdate, add_days,nowdate
from frappe.model.document import Document

class InsuranceClaimSubmission(Document):
	def on_submit(self):
		self.update_claim_details()
		self.create_submission_jv()
		self.reload()
	def on_cancel(self):
		if self.insurance_claim_submission_item:
			for item in self.insurance_claim_submission_item:
				insurance_claim= frappe.get_doc("Insurance Claim",item.insurance_claim)
				if insurance_claim:
					claim_submitted_jv = insurance_claim.claim_submitted_jv
					insurance_claim.submitted_by = ""
					insurance_claim.submitted_on = ""
					insurance_claim.claim_status = "Claim Created"
					insurance_claim.approved_amount = 0
					insurance_claim.claim_submitted_jv = ""
					insurance_claim.save(ignore_permissions=True)
					if claim_submitted_jv:
						jv_obj = frappe.get_doc("Journal Entry", claim_submitted_jv)
						jv_obj.cancel()
		jv = frappe.db.exists("Journal Entry",
			{
				'name': self.claim_submission_jv
			})
		if jv:
			jv_obj = frappe.get_doc("Journal Entry", jv)
			jv_obj.cancel()
	def update_claim_details(self):
		if self.insurance_claim_submission_item:
			for item in self.insurance_claim_submission_item:
				insurance_claim= frappe.get_doc("Insurance Claim",item.insurance_claim)
				if insurance_claim:
					frappe.db.set_value("Insurance Claim", insurance_claim.name, "submitted_by", frappe.session.user)
					frappe.db.set_value("Insurance Claim", insurance_claim.name, "submitted_on", nowdate())
					frappe.db.set_value("Insurance Claim", insurance_claim.name, "claim_status", "Claim Submitted")
				frappe.db.set_value("Insurance Claim Submission Item", item.name, "claim_status", "Claim Submitted")

	def complete(self):
		if self.insurance_claim_submission_item:
			self.update_final_claim_details()
		self.create_journal_entry_final_submission()
		self.is_finished=1
		self.save()

	def create_submission_jv(self):
		# create jv
		insurance_company = frappe.get_doc('Insurance Company', self.insurance_company)
		from erpnext.accounts.party import get_party_account
		journal_entry = frappe.new_doc('Journal Entry')
		if frappe.db.get_value("Healthcare Settings", None, "journal_entry_type"):
			journal_entry.voucher_type =frappe.db.get_value("Healthcare Settings", None, "journal_entry_type")
		else:
			journal_entry.voucher_type = 'Journal Entry'
		if frappe.db.get_value("Healthcare Settings", None, "journal_entry_series"):
			journal_entry.naming_series =frappe.db.get_value("Healthcare Settings", None, "journal_entry_series")
		journal_entry.company = insurance_company.company
		journal_entry.posting_date =  nowdate()
		accounts = []
		tax_amount = 0.0
		accounts.append({
				"account": insurance_company.pre_claim_receivable_account,
				"credit_in_account_currency": self.total_claim_amount,
				"party_type": "Customer",
				"party": insurance_company.customer,
			})
		accounts.append({
				"account": insurance_company.submission_claim_receivable_account,
				"debit_in_account_currency": self.total_claim_amount,
				"party_type": "Customer",
				"party": insurance_company.customer,
			})
		journal_entry.set("accounts", accounts)
		journal_entry.save(ignore_permissions = True)
		journal_entry.submit()
		frappe.db.set_value("Insurance Claim Submission", self.name, "claim_submission_jv", journal_entry.name)

	def create_journal_entry_final_submission(self):
		# create jv
		insurance_company = frappe.get_doc('Insurance Company', self.insurance_company)
		from erpnext.accounts.party import get_party_account
		journal_entry = frappe.new_doc('Journal Entry')
		if frappe.db.get_value("Healthcare Settings", None, "journal_entry_type"):
			journal_entry.voucher_type =frappe.db.get_value("Healthcare Settings", None, "journal_entry_type")
		else:
			journal_entry.voucher_type = 'Journal Entry'
		if frappe.db.get_value("Healthcare Settings", None, "journal_entry_series"):
			journal_entry.naming_series =frappe.db.get_value("Healthcare Settings", None, "journal_entry_series")
		journal_entry.company = insurance_company.company
		journal_entry.posting_date =  nowdate()
		accounts = []
		tax_amount = 0.0
		accounts.append({
			"account": insurance_company.submission_claim_receivable_account,
			"credit_in_account_currency":float(self.total_claim_amount),
			"party_type": "Customer",
			"party": insurance_company.customer
		})
		accounts.append({
			"account": get_party_account("Customer", insurance_company.customer, insurance_company.company),
			"debit_in_account_currency": float(self.total_approved_amount),
			"party_type": "Customer",
			"party": insurance_company.customer
		})
		accounts.append({
			"account": insurance_company.insurance_rejected_expense_account,
			"debit_in_account_currency": float(self.total_rejected_amount),
			"party_type": "Customer",
			"party": insurance_company.customer
		})
		journal_entry.set("accounts", accounts)
		journal_entry.save(ignore_permissions = True)
		journal_entry.submit()
		self.claim_approved_jv=journal_entry.name

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
	def update_final_claim_details(doc):
		submittted_claim=[]
		from six import string_types
		if isinstance(doc, string_types):
			doc =  json.loads(doc)
		for claim in doc.insurance_claim_submission_item:
			if isinstance(claim, dict):
				claim = frappe._dict(claim)
			frappe.db.set_value("Insurance Claim Item", claim.insurance_claim_item, "claim_status", claim.claim_status)
			frappe.db.set_value("Insurance Claim Item", claim.insurance_claim_item, "approved_amount", claim.approved_amount)
			frappe.db.set_value("Insurance Claim Item", claim.insurance_claim_item, "rejected_amount", claim.rejected_amount)
			if claim.insurance_claim not in submittted_claim:
				submittted_claim.append(claim.insurance_claim)
		for sub_claim in submittted_claim:
			insurance_claim=frappe.get_doc("Insurance Claim", sub_claim)
			insurance_claim.submission_date=nowdate()
			insurance_claim.save()
		return True

@frappe.whitelist()
def get_claim_submission_item(insurance_company, from_date=False, to_date=False):
	query = """
		select
			name
		from
			`tabInsurance Claim`
		where
			insurance_company='{0}' and docstatus=1  and claim_status="Claim Created"
	"""
	if from_date:
		query += """ and created_on >=%(from_date)s"""
	if to_date:
		query += """ and created_on <=%(to_date)s"""
	claim_list = frappe.db.sql(query.format(insurance_company),{
			'from_date': from_date, 'to_date':to_date
		}, as_dict=True)
	claim_list_obj = []
	if claim_list:
		for claim in claim_list:
			claim_list_obj.append(frappe.get_doc("Insurance Claim", claim.name))
	if claim_list_obj and len(claim_list_obj)>0:
		return claim_list_obj
	return False


	