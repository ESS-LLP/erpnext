# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class LabTestNormalRange(Document):
	def validate(self):
		self.validate_normal_condition()

	def validate_normal_condition(self):
		if self.normal_range_condition:
			for item in self.normal_range_condition:
				if not item.gender and not(item.condition_field and item.condition_formula):
					frappe.throw(_("Required Gender or Condition Field and Condition/Formula"))
