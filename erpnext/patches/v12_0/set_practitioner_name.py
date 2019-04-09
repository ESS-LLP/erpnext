from __future__ import unicode_literals
import frappe
from frappe import _

def execute():
	if "Healthcare" not in frappe.get_active_domains():
		return

	frappe.reload_doc("healthcare", "doctype", "healthcare_practitioner")
	if frappe.db.has_column("Healthcare Practitioner", 'practitioner_name'):
		for doc in frappe.get_all('Healthcare Practitioner'):
			frappe.get_doc('Healthcare Practitioner', doc.name).save()
