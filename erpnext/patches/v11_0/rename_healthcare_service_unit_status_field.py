import frappe
from frappe.model.utils.rename_field import rename_field

def execute():
	if "Healthcare" not in frappe.get_active_domains():
		return

	if frappe.db.exists('DocType', 'Healthcare Service Unit'):
		if frappe.db.has_column('Healthcare Service Unit', 'occupancy_status'):
			rename_field('Healthcare Service Unit', 'occupancy_status', 'status')
