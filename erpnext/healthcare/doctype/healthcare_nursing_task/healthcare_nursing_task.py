# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class HealthcareNursingTask(Document):
	def on_update(self):
		if self.status:
			clinical_procedure = frappe.get_doc('Clinical Procedure', self.reference_docname)
			for nursing_tasks in clinical_procedure.nursing_tasks:
				if nursing_tasks.check_list == self.task:
					nursing_tasks.status = self.status
					nursing_tasks.save(ignore_permissions=True)

