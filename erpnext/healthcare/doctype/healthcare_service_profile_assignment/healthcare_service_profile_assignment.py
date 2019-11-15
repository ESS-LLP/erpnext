# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class HealthcareServiceProfileAssignment(Document):
	def validate(self):
		if self.is_active:
			assignment = frappe.db.exists("Healthcare Service Profile Assignment",
			{
				'practitioner': self.practitioner,
				'is_active': 1
			})
			if assignment and assignment != self.name:
				frappe.throw(_("There exist an active Service Profile Assignment with this practitioner {0}").format(self.practitioner))

