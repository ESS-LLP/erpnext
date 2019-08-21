from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("healthcare", "doctype", "clinical_procedure")
