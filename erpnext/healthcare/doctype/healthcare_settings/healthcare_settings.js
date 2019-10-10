// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Healthcare Settings', {
	setup: function(frm) {
		frm.set_query('account', 'receivable_account', function(doc, cdt, cdn) {
			var d  = locals[cdt][cdn];
			return {
				filters: {
					'account_type': 'Receivable',
					'company': d.company,
					'is_group': 0
				}
			};
		});
		frm.set_query('account', 'income_account', function(doc, cdt, cdn) {
			var d  = locals[cdt][cdn];
			return {
				filters: {
					'root_type': 'Income',
					'company': d.company,
					'is_group': 0
				}
			};
		});
		set_query_service_item(frm, 'inpatient_visit_charge_item');
		set_query_service_item(frm, 'op_consulting_charge_item');
		set_query_service_item(frm, 'clinical_procedure_consumable_item');
		frappe.model.with_doctype("Journal Entry", function() {
			let options = frappe.get_meta("Journal Entry").fields.filter(d => d.fieldname=='voucher_type')[0].options;
			let default_value = frappe.get_meta("Journal Entry").fields.filter(d => d.fieldname=='voucher_type')[0].default;
			if(!frm.doc.journal_entry_type){
				frm.set_value("journal_entry_type", default_value);
			}
			frm.set_df_property("journal_entry_type", "options", options);
		});
		frappe.model.with_doctype("Journal Entry", function() {
			let options = frappe.get_meta("Journal Entry").fields.filter(d => d.fieldname=='naming_series')[0].options;
			let default_value = frappe.get_meta("Journal Entry").fields.filter(d => d.fieldname=='naming_series')[0].default;
			if(!frm.doc.journal_entry_series){
				frm.set_value("journal_entry_series", default_value);
			}
			frm.set_df_property("journal_entry_series", "options", options);
		});
	}
});

var set_query_service_item = function(frm, service_item_field) {
	frm.set_query(service_item_field, function() {
		return {
			filters: {
				'is_sales_item': 1,
				'is_stock_item': 0
			}
		};
	});
};
