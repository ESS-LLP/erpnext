from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.utils.rename_field import rename_field

def execute():
	""" assign lft and rgt appropriately """
	if "Healthcare" not in frappe.get_active_domains():
		return

	frappe.reload_doc("healthcare", "doctype", "medical_department")

	if frappe.db.exists('DocType', "Medical Department"):
		frappe.db.sql("""
			update
				`tabMedical Department`
			set
				parent_medical_department = 'All Medical Departments'
			where
				is_group != 1
		""")
		if frappe.db.has_column("Medical Department", "department"):
			rename_field("Medical Department", "department", "medical_department_name")

	frappe.get_doc({
		'doctype': 'Medical Department',
		'medical_department_name': _('All Medical Departments'),
		'is_group': 1,
	}).insert(ignore_permissions=True)
