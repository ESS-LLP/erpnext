// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
{% include 'erpnext/healthcare/healthcare_doc_item.js' %}

frappe.ui.form.on('Radiology Procedure', {
	refresh: function(frm) {
		item_action_buttons(frm);
		frm.set_query("medical_department", function() {
			return {
				filters: {
					'is_diagnostic_speciality': true,
					'is_group': false
				}
			};
		});
	},
	procedure_name: function(frm) {
		if(!frm.doc.item_code)
			frm.set_value("item_code", frm.doc.procedure_name);
		if(!frm.doc.description)
			frm.set_value("description", frm.doc.procedure_name);
	},
});
