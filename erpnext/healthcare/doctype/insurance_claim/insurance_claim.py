# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import time_diff_in_hours, rounded, getdate, add_days,nowdate
from frappe.model.document import Document

class InsuranceClaim(Document):
	def on_submit(self):
		self.create_journal_entry_insurance_claim()
		frappe.db.set_value("Insurance Claim", self.name, "claim_status", "Claim Created")
	def on_update_after_submit(self):
		if self.claim_status == "Claim Approved":
			self.create_journal_entry_finished_submission()
		frappe.db.set_value("Insurance Claim", self.name, "claim_status", "Claim Approved")
	def create_journal_entry_insurance_claim(self):
			# create jv
			sales_invoice = frappe.get_doc('Sales Invoice', self.sales_invoice)
			insurance_company = frappe.get_doc('Insurance Company', self.insurance_company)
			from erpnext.accounts.party import get_party_account
			journal_entry = frappe.new_doc('Journal Entry')
			journal_entry.voucher_type = 'Journal Entry'
			journal_entry.company = sales_invoice.company
			journal_entry.posting_date =  nowdate()
			accounts = []
			tax_amount = 0.0
			accounts.append({
					"account": get_party_account("Customer", sales_invoice.customer, sales_invoice.company),
					"credit_in_account_currency": self.claim_amount,
					"party_type": "Customer",
					"party": sales_invoice.customer,
					"reference_type": sales_invoice.doctype,
					"reference_name": sales_invoice.name
				})
			accounts.append({
					"account": insurance_company.pre_claim_submission_account,
					"debit_in_account_currency": self.claim_amount,
					"party_type": "Customer",
					"party": insurance_company.customer,
				})
			journal_entry.set("accounts", accounts)
			journal_entry.save(ignore_permissions = True)
			journal_entry.submit()
			frappe.db.set_value("Insurance Claim", self.name, "cliam_created__jv", journal_entry.name)

	def create_journal_entry_finished_submission(self):
			# create jv
			sales_invoice = frappe.get_doc('Sales Invoice', self.sales_invoice)
			insurance_company = frappe.get_doc('Insurance Company', self.insurance_company)
			from erpnext.accounts.party import get_party_account
			journal_entry = frappe.new_doc('Journal Entry')
			journal_entry.voucher_type = 'Journal Entry'
			journal_entry.company = insurance_company.company
			journal_entry.posting_date =  nowdate()
			accounts = []
			tax_amount = 0.0
			accounts.append({
				"account": insurance_company.submission_claim_account,
				"credit_in_account_currency":float(self.claim_amount),
				"party_type": "Customer",
				"party": insurance_company.customer
			})
			accounts.append({
				"account": get_party_account("Customer", insurance_company.customer, insurance_company.company),
				"debit_in_account_currency": float(self.claim_amount)+tax_amount,
				"party_type": "Customer",
				"party": insurance_company.customer
			})
			journal_entry.set("accounts", accounts)
			journal_entry.save(ignore_permissions = True)
			journal_entry.submit()
			frappe.db.set_value("Insurance Claim", self.name, "claim_submitted_jv", journal_entry.name)

