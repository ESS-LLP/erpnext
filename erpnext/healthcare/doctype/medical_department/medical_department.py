# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS LLP and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from frappe.utils.nestedset import NestedSet
import frappe

class MedicalDepartment(NestedSet):
	nsm_parent_field = 'parent_medical_department'

	def on_update(self):
		super(MedicalDepartment, self).on_update()
		self.validate_one_root()
