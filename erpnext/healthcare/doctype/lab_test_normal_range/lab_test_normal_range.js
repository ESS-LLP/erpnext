// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Lab Test Normal Range', {
	refresh: function(frm) {
		set_options_for_child_fields(frm);
	}
});

var set_options_for_child_fields = function(frm) {
	var options = "";
	frappe.model.with_doctype("Patient", function() {
		var meta = frappe.get_meta("Patient");
		options = meta.fields.filter(df =>
			!df.hidden && (df.fieldtype == "Data" || df.fieldtype == "Float" || df.fieldtype == "Check" || df.fieldtype == "Int"
			|| df.fieldtype == "Date" || df.fieldtype == "Datetime" || df.fieldtype == "Dynamic Link" || df.fieldtype == "Link"
			|| df.fieldtype == "Long Text" || df.fieldtype == "Read Only" || df.fieldtype == "Select" || df.fieldtype == "Text"
			|| df.fieldtype == "Text Editor" || df.fieldtype == "Time" || df.fieldtype == "Small Text")
		).map(df => df.fieldname);
		var df = frappe.meta.get_docfield("Lab Test Normal Range Condition", "condition_field", frm.doc.name);
		df.options = options;
	});
};

frappe.ui.form.on('Lab Test Normal Range Condition', {
	based_on: function(frm, cdt, cdn) {
		var child = locals[cdt][cdn];
		if(child.based_on && child.based_on=="Age"){
			if(child.condition_field!="dob"){
				frappe.model.set_value(cdt, cdn, 'condition_field', 'dob');
			}
		}
		else if(!child.based_on){
			frappe.model.set_value(cdt, cdn, 'condition_field', '');
		}
	}
});
