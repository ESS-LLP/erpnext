from __future__ import unicode_literals
import frappe

def execute():
	frappe.db.sql("alter table `tabClinical Procedure` change standard_selling_rate standard_selling_rate decimal(18,6) default '0.0'")
	frappe.reload_doc("healthcare", "doctype", "clinical_procedure")
