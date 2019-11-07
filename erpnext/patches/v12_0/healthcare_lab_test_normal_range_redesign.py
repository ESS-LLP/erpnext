from __future__ import unicode_literals
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from erpnext.domains.healthcare import data

def execute():
	if "Healthcare" not in frappe.get_active_domains():
		return

	doctypes = ['lab_test_template', 'normal_test_template', 'lab_test_groups', 'lab_test_normal_range', 'lab_test_normal_range_condition']
	for doctype in doctypes:
		frappe.reload_doc('healthcare', 'doctype', doctype)

	lab_test_template_types = ["Single", "Compound", "Grouped"]
	for template_type in lab_test_template_types:
		lab_test_template = frappe.get_list("Lab Test Template", filters={"lab_test_template_type": template_type}, fields=["name"])
		for d in lab_test_template:
			template = frappe.get_doc("Lab Test Template", d.name)
			female_normal_range = False
			if frappe.db.has_column("Lab Test Template", "abbr") and not template.abbr:
				template.abbr = template.lab_test_name
			if template_type == "Single" and template.lab_test_normal_range:
				normal_range_name = '-'.join(filter(lambda x: x, [template.lab_test_name, template.lab_test_normal_range]))
				if frappe.db.has_column("Lab Test Template", "lab_test_normal_range_female") and template.lab_test_normal_range_female:
					female_normal_range = template.lab_test_normal_range_female
				template.lab_test_normal_range = create_lab_test_normal_range(template, template.lab_test_normal_range, normal_range_name, female_normal_range)
			elif template_type == "Compound" and template.normal_test_templates:
				for normal_test_template in template.normal_test_templates:
					if normal_test_template.normal_range:
						normal_range_name = '-'.join(filter(lambda x: x, [normal_test_template.lab_test_event, normal_test_template.normal_range]))
						if frappe.db.has_column("Normal Test Template", "normal_range_female") and normal_test_template.normal_range_female:
							female_normal_range = normal_test_template.normal_range_female
						normal_test_template.normal_range = create_lab_test_normal_range(template, normal_test_template.normal_range, normal_range_name, female_normal_range)
			elif template_type == "Grouped" and template.lab_test_groups:
				for lab_test_group in template.lab_test_groups:
					if lab_test_group.group_test_normal_range:
						normal_range_name = '-'.join(filter(lambda x: x, [lab_test_group.group_event, lab_test_group.group_test_normal_range]))
						lab_test_group.group_test_normal_range = create_lab_test_normal_range(template, lab_test_group.group_test_normal_range, normal_range_name)
			template.save(ignore_permissions=True)

def create_lab_test_normal_range(template, normal_range, normal_range_name, female_normal_range=False):
	lab_test_normal_range_id = frappe.db.exists(
		"Lab Test Normal Range",
		{"name": normal_range_name}
	)
	if lab_test_normal_range_id:
		if female_normal_range:
			lab_test_normal_range = frappe.get_doc("Lab Test Normal Range", lab_test_normal_range_id)
			normal_range_condition = lab_test_normal_range.append("normal_range_condition")
			normal_range_condition.gender = "Female"
			normal_range_condition.normal_range = female_normal_range
			lab_test_normal_range.save(ignore_permissions=True)
		return lab_test_normal_range_id
	else:
		lab_test_normal_range = frappe.new_doc("Lab Test Normal Range")
		lab_test_normal_range.lab_test_normal_range = normal_range_name
		lab_test_normal_range.default_normal_range = normal_range
		if female_normal_range:
			normal_range_condition = lab_test_normal_range.append("normal_range_condition")
			normal_range_condition.gender = "Female"
			normal_range_condition.normal_range = female_normal_range
		lab_test_normal_range.save(ignore_permissions=True)
		return lab_test_normal_range.name
