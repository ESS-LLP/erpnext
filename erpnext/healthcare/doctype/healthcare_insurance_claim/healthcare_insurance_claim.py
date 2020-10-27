# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class HealthcareInsuranceClaim(Document):
	def on_update_after_submit(self):
		if self.claim_status != 'Pending':
			update_claim_status_to_service(self)

def update_claim_status_to_service(doc):
	service_name = frappe.db.exists(doc.service_doctype,
	{
		'insurance_claim': doc.name,
		'claim_status': 'Pending'
	})
	if service_name:
		frappe.db.set_value(doc.service_doctype, service_name, 'claim_status', doc.claim_status)
