# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
# import frappe
from frappe.model.document import Document

class InsuranceContract(Document):
	def validate(self):
		if self.is_active:
			contract = frappe.db.exists('Insurance Contract',
			{
				'insurance_company': self.insurance_company,
				'start_date':("<=", getdate(nowdate())),
				'end_date':(">=", getdate(nowdate())),
				'is_active': 1
			})
			if contract and contract != self.name:
				frappe.throw(_('There exist an active contract with this insurance company {0}').format(contract))
