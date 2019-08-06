from __future__ import unicode_literals
import frappe
from frappe import _

def execute():
	if "Healthcare" not in frappe.get_active_domains():
		return

	frappe.reload_doc("healthcare", "doctype", "clinical_procedure")
	clinical_procedure_list = frappe.get_all("Clinical Procedure", fields=["name"], filters = {'status': ["in", ["In Progress", "Completed"]]})
	if clinical_procedure_list:
		for clinical_procedure_id in clinical_procedure_list:
			frappe.get_doc("Clinical Procedure", clinical_procedure_id.name).submit()
