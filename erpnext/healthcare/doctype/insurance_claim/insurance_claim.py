# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _, msgprint, throw
from frappe.utils import time_diff_in_hours, rounded, getdate, add_days,nowdate
from frappe.model.document import Document

class InsuranceClaim(Document):
	def on_submit(self):
		self.create_journal_entry_insurance_claim()
		frappe.db.set_value("Insurance Claim", self.name, "claim_status", "Claim Created")
	def on_before_cancel(self):
		if self.claim_status!="Claim Created":
			frappe.throw(_("Submitted Clain can not cancel"))
		jv = frappe.db.exists("Journal Entry",
			{
				'name': self.claim_created_jv
			})
		if jv:
			jv_obj = frappe.get_doc("Journal Entry", jv)
			jv_obj.cancel()
	def on_update_after_submit(self):
		self.calculate_total_approved_rejected_amount()

	def create_journal_entry_insurance_claim(self):
			# create jv
			sales_invoice = frappe.get_doc('Sales Invoice', self.sales_invoice)
			insurance_company = frappe.get_doc('Insurance Company', self.insurance_company)
			from erpnext.accounts.party import get_party_account
			journal_entry = frappe.new_doc('Journal Entry')
			if frappe.db.get_value("Healthcare Settings", None, "journal_entry_type"):
				journal_entry.voucher_type =frappe.db.get_value("Healthcare Settings", None, "journal_entry_type")
			else:
				journal_entry.voucher_type = 'Journal Entry'
			if frappe.db.get_value("Healthcare Settings", None, "journal_entry_series"):
				journal_entry.naming_series =frappe.db.get_value("Healthcare Settings", None, "journal_entry_series")
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
					"account": insurance_company.pre_claim_receivable_account,
					"debit_in_account_currency": self.claim_amount,
					"party_type": "Customer",
					"party": insurance_company.customer,
				})
			journal_entry.set("accounts", accounts)
			journal_entry.save(ignore_permissions = True)
			journal_entry.submit()
			frappe.db.set_value("Insurance Claim", self.name, "claim_created_jv", journal_entry.name)

	def calculate_total_approved_rejected_amount(self):
		total_approved_amount=0
		total_rejected_amount=0
		if self.insurance_claim_item:
			for claim_item in self.insurance_claim_item:
				if claim_item.approved_amount:
					total_approved_amount=total_approved_amount+claim_item.approved_amount
				if claim_item.rejected_amount:
					total_rejected_amount=total_rejected_amount+claim_item.rejected_amount
			if total_approved_amount:
				frappe.db.set_value("Insurance Claim", self.name, "approved_amount", total_approved_amount)
			if total_rejected_amount:
				frappe.db.set_value("Insurance Claim", self.name, "rejected_amount", total_rejected_amount)

