// Copyright (c) 2016, ESS
// License: ESS license.txt

frappe.ui.form.on("Lab Test Template",{
	lab_test_name: function(frm) {
		if(!frm.doc.lab_test_code)
			frm.set_value("lab_test_code", frm.doc.lab_test_name);
		if(!frm.doc.lab_test_description)
			frm.set_value("lab_test_description", frm.doc.lab_test_name);
	},
	refresh :  function(frm){
		if(!frm.doc.__islocal) {
			frm.set_df_property("abbr", "read_only", 1);
		}
		// Restrict Special, Grouped type templates in Child TestGroups
		frm.set_query("lab_test_template", "lab_test_groups", function() {
			return {
				filters: {
					lab_test_template_type:['in',['Single','Compound', 'Descriptive']]
				}
			};
		});
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
				method: "erpnext.healthcare.doctype.lab_test_template.lab_test_template.replace_abbr",
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
});

cur_frm.cscript.custom_refresh = function(doc) {
	cur_frm.set_df_property("lab_test_code", "read_only", doc.__islocal ? 0 : 1);

	if(!doc.__islocal) {
		cur_frm.add_custom_button(__('Change Template Code'), function() {
			change_template_code(cur_frm,doc);
		} );
		if(doc.disabled == 1){
			cur_frm.add_custom_button(__('Enable Template'), function() {
				enable_template(cur_frm);
			} );
		}
		else{
			cur_frm.add_custom_button(__('Disable Template'), function() {
				disable_template(cur_frm);
			} );
		}
	}
};

var disable_template = function(frm){
	var doc = frm.doc;
	frappe.call({
		method: 		"erpnext.healthcare.doctype.lab_test_template.lab_test_template.disable_enable_test_template",
		args: {status: 1, name: doc.name, is_billable: doc.is_billable},
		callback: function(){
			cur_frm.reload_doc();
		}
	});
};

var enable_template = function(frm){
	var doc = frm.doc;
	frappe.call({
		method: 		"erpnext.healthcare.doctype.lab_test_template.lab_test_template.disable_enable_test_template",
		args: {status: 0, name: doc.name, is_billable: doc.is_billable},
		callback: function(){
			cur_frm.reload_doc();
		}
	});
};


var change_template_code = function(frm,doc){
	var d = new frappe.ui.Dialog({
		title:__("Change Template Code"),
		fields:[
			{
				"fieldtype": "Data",
				"label": "Test Template Code",
				"fieldname": "Test Code",
				reqd:1
			},
			{
				"fieldtype": "Button",
				"label": __("Change Code"),
				click: function() {
					var values = d.get_values();
					if(!values)
						return;
					change_test_code_from_template(values["Test Code"],doc);
					d.hide();
				}
			}
		]
	});
	d.show();
	d.set_values({
		'Test Code': doc.lab_test_code
	});

	var change_test_code_from_template = function(lab_test_code,doc){
		frappe.call({
			"method": "erpnext.healthcare.doctype.lab_test_template.lab_test_template.change_test_code_from_template",
			"args": {lab_test_code: lab_test_code, doc: doc},
			callback: function (data) {
				frappe.set_route("Form", "Lab Test Template", data.message);
			}
		});
	};
};

frappe.ui.form.on("Lab Test Template", "lab_test_name", function(frm){

	frm.doc.change_in_item = 1;

});
frappe.ui.form.on("Lab Test Template", "lab_test_rate", function(frm){

	frm.doc.change_in_item = 1;

});
frappe.ui.form.on("Lab Test Template", "lab_test_group", function(frm){

	frm.doc.change_in_item = 1;

});
frappe.ui.form.on("Lab Test Template", "lab_test_description", function(frm){

	frm.doc.change_in_item = 1;

});

frappe.ui.form.on("Lab Test Groups", "template_or_new_line", function (frm, cdt, cdn) {
	var child = locals[cdt][cdn];
	if(child.template_or_new_line =="Add new line"){
		frappe.model.set_value(cdt, cdn, 'lab_test_template', "");
		frappe.model.set_value(cdt, cdn, 'lab_test_description', "");
	}
});
