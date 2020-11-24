# -*- coding: utf-8 -*-
# Copyright (c) 2020, earthians and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class HealthcareServiceOrder(Document):
	def after_insert(self):
		make_insurance_claim(self)
	def validate(self):
		if self.insurance_subscription and self.claim_status == 'Pending':
			self.status = 'Waiting'
def make_insurance_claim(doc):
	if doc.insurance_subscription and not doc.insurance_claim:
		from erpnext.healthcare.utils import create_insurance_claim
		insurance_claim, claim_status = create_insurance_claim(doc, doc.order_doctype, doc.order, doc.quantity, doc.billing_item)
		if insurance_claim:
			frappe.set_value(doc.doctype, doc.name ,'insurance_claim', insurance_claim)
			frappe.set_value(doc.doctype, doc.name ,'claim_status', claim_status)
			doc.reload()
