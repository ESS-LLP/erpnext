    # -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from erpnext.healthcare.utils import create_item_from_doc, update_item_from_doc, on_trash_doc_having_item_reference

class RadiologyExaminationTemplate(Document):
	def validate(self):
		update_item_from_doc(self, self.procedure_name)

	def after_insert(self):
		create_item_from_doc(self, self.procedure_name)

	def on_trash(self):
		on_trash_doc_having_item_reference(self)

