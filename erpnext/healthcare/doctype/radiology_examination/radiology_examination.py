# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class RadiologyExamination(Document):
	pass
@frappe.whitelist()
def get_radiology_procedure_prescribed(patient):
	return frappe.db.sql("""select cp.name, cp.radiology_procedure_name, cp.parent, cp.invoiced,  ct.encounter_date, ct.source, ct.referring_practitioner from `tabPatient Encounter` ct,
	`tabRadiology Procedure Prescription` cp where ct.patient=%s and cp.parent=ct.name and cp.radiology_examination_created=0""", (patient))
