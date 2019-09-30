// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
{% include 'erpnext/healthcare/healthcare_doc_item.js' %}

frappe.ui.form.on('Radiology Procedure', {
	refresh: function(frm) {
		if(!frm.doc.__islocal) {
			frm.set_df_property("abbr", "read_only", 1);
		}
		item_action_buttons(frm);
	},
	change_abbr : function(frm) {
		var dialog = new frappe.ui.Dialog({
			title: "Replace Abbr",
			fields: [
				{"fieldtype": "Data", "label": "New Abbreviation", "fieldname": "new_abbr",
					"reqd": 1 },
				{"fieldtype": "Button", "label": "Update", "fieldname": "update"},
			]
		});

		dialog.fields_dict.update.$input.click(function() {
			var args = dialog.get_values();
			if(!args) return;
			frappe.show_alert(__("Update in progress. It might take a while."));
			return frappe.call({
				method: "erpnext.healthcare.doctype.radiology_procedure.radiology_procedure.replace_abbr",
				args: {
					"name": frm.doc.name,
					"old": frm.doc.abbr,
					"new": args.new_abbr
				},
				callback: function(r) {
					if(r.exc) {
						frappe.msgprint(__("There were errors."));
						return;
					} else {
						frm.set_value("abbr", args.new_abbr);
					}
					dialog.hide();
					frm.refresh();
				},
				btn: this
			})
		});
		dialog.show();
	},
	procedure_name: function(frm) {
		if(!frm.doc.item_code)
			frm.set_value("item_code", frm.doc.procedure_name);
		if(!frm.doc.description)
			frm.set_value("description", frm.doc.procedure_name);
	},
});
