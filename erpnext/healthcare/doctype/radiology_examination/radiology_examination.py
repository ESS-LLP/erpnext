# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from erpnext.healthcare.utils import manage_healthcare_doc_cancel

class RadiologyExamination(Document):
	def on_cancel(self):
		manage_healthcare_doc_cancel(self)

@frappe.whitelist()
def get_radiology_procedure_prescribed(patient, encounter_practitioner=False):
	query = """
		select
			cp.name, cp.radiology_procedure_name, cp.parent, cp.invoiced, ct.encounter_date, ct.source, ct.referring_practitioner,
			ct.practitioner, ct.insurance
		from
			`tabPatient Encounter` ct, `tabRadiology Procedure Prescription` cp
		where
			ct.patient='{0}' and cp.parent=ct.name and cp.radiology_examination_created=0
	"""
	if encounter_practitioner:
		query +=""" and ct.practitioner=%(encounter_practitioner)s"""

	query +="""
		order by
			ct.creation desc"""

	return frappe.db.sql(query.format(patient),{
		"encounter_practitioner": encounter_practitioner
	})
