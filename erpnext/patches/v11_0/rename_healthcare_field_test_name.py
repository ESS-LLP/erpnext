import frappe
from frappe.model.utils.rename_field import rename_field
from frappe.modules import scrub, get_doctype_module

field_rename_docs = ["Lab Test Template", "Normal Test Items", "Lab Test", "Lab Prescription"]

def execute():
	for dn in field_rename_docs:
		if frappe.db.exists('DocType', dn):
			frappe.reload_doc(get_doctype_module(dn), "doctype", scrub(dn))
			if frappe.db.has_column(dn, "test_name"):
				rename_field(dn, "test_name", "lab_test_name")
