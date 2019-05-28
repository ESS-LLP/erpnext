from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from erpnext.domains.healthcare import data

def execute():
	if data['custom_fields']:
		create_custom_fields(data['custom_fields'])
