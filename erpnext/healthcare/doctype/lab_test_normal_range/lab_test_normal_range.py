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
				if not item.gender and not(item.based_on and item.condition_field and item.condition_formula):
					frappe.throw(_("Required Gender or Based on and Condition Field and Condition/Formula"))
				elif item.gender and not(item.based_on and item.condition_field and item.condition_formula) and (item.based_on or item.condition_field or item.condition_formula):
					frappe.throw(_("Required Based on and Condition Field and Condition/Formula"))
				if item.based_on and item.based_on == "Age" and item.condition_field != "dob":
					item.condition_field = "dob"
