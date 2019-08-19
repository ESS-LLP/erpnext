// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Insurance Company', {
	refresh: function(frm) {
		frappe.dynamic_link = {doc: frm.doc, fieldname: 'name', doctype: 'Insurance Company'}

		if(frm.doc.__islocal){
			hide_field(['address_html', 'contact_html', 'address_contacts']);
			frappe.contacts.clear_address_and_contact(frm);
		}
		else{
			unhide_field(['address_html', 'contact_html', 'address_contacts']);
			frappe.contacts.render_address_and_contact(frm);
		}
		frm.set_query("pre_claim_submission_account", function() {
			return {
				filters: {
					'account_type': 'Receivable',
					'company': frm.doc.company,
					"is_group": 0
				}
			};
		});
		frm.set_query("submission_claim_account", function() {
			return {
				filters: {
					'account_type': 'Receivable',
					'company': frm.doc.company,
					"is_group": 0
				}
			};
		});
		frm.set_query("adjustment_accounts", function() {
			return {
				filters: {
					'account_type': 'Receivable',
					'company': frm.doc.company,
					"is_group": 0
				}
			};
		});
	}
});
