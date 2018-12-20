# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class PractitionerEvent(Document):
	def validate(self):
		self.validate_repeat_on()

	def validate_repeat_on(self):
		if self.repeat_on == "Every Day":
			have_atleast_one_weekday = False
			weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
			for weeday in weekdays:
				if self.get(weeday) == 1:
					have_atleast_one_weekday = True
			if not have_atleast_one_weekday:
				frappe.throw("Please select atleast one day")
