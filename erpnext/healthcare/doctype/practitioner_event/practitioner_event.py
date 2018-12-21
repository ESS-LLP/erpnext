# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import time_diff_in_seconds
from frappe import _
from frappe.model.document import Document

class PractitionerEvent(Document):
	def validate(self):
		self.validate_repeat_on()
		if self.present == 1:
			validate_duration(self)

	def validate_repeat_on(self):
		if self.repeat_on == "Every Day":
			have_atleast_one_weekday = False
			weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
			for weeday in weekdays:
				if self.get(weeday) == 1:
					have_atleast_one_weekday = True
			if not have_atleast_one_weekday:
				frappe.throw("Please select atleast one day")

def validate_duration(doc):
	if doc.duration <= 0:
		frappe.throw(_("Duration must be geater than zero"))
	else:
		# time diff in minutes = in seconds / 60
		total_time_diff = time_diff_in_seconds(doc.to_time, doc.from_time)/60
		if total_time_diff <= 0:
			frappe.throw(_("From Time should not be greater than or equal to To Time"))
		if total_time_diff < doc.duration:
			frappe.throw(_("Duration between from time and to time must be greater than or equal to duration given"))
		elif total_time_diff % doc.duration != 0:
			frappe.throw(_("Duration between from time and to time must be multiple of duration given"))
