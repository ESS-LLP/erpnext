	# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class MedicoLegalRecord(Document):
	def after_insert(self):
		if self.emergency_patient_record:
			frappe.db.set_value("Emergency Patient Record", self.emergency_patient_record, "medico_legal_record_created", 1)
