# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class HealthcareServiceInsuranceCoverage(Document):
	def validate(self):
		self.validate_service_overlap()

	def validate_service_overlap(self):
		service_insurance_coverages = frappe.db.get_list('Healthcare Service Insurance Coverage',
											{
											'healthcare_insurance_coverage_plan': self.healthcare_insurance_coverage_plan,
											'is_active': 1,
											'healthcare_service_template' : self.healthcare_service_template,
											'end_date':['<=', self.end_date]
											})
		if len(service_insurance_coverages) > 0:
			frappe.throw(_('Service {0} activated  this coverage plan {1}').format(frappe.bold(self.healthcare_service_template),
				frappe.bold(self.healthcare_insurance_coverage_plan)), title=_('Not Allowed'))
