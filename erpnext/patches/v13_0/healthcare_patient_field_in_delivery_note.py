from __future__ import unicode_literals
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from erpnext.domains.healthcare import data

def execute():
    frappe.reload_doc('stock', 'doctype', 'delivery_note')

    if "Healthcare" not in frappe.get_active_domains():
        return

    if data['custom_fields']:
        create_custom_fields(data['custom_fields'])
