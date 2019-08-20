// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Insurance Claim', {
	setup:function(frm){
		frm.set_query("sales_invoice", function() {
			return {
				filters: {
					patient: frm.doc.patient
				}
			};
		});
		frm.set_query("insurance_assignment", function() {
			return {
				filters: {
					patient: frm.doc.patient
				}
			};
		});
	},
	sales_invoice: function(frm) {
		if(frm.doc.sales_invoice){
			frappe.call({
				"method": "frappe.client.get",
				args: {
					doctype: "Sales Invoice",
					name: frm.doc.sales_invoice
				},
				callback: function (data) {
					frm.set_value("bill_amount", data.message.amount);
					frm.refresh_fields()
				}
			});
		}
	},
	insurance_assignment: function(frm) {
		if(frm.doc.insurance_assignment){
			frappe.call({
				"method": "frappe.client.get",
				args: {
					doctype: "Insurance Assignment",
					name: frm.doc.insurance_assignment
				},
				callback: function (data) {
					frm.set_value("insurance_company", data.message.insurance_company);
					frm.set_value("insurance_company", data.message.claim_percentage);
					frm.refresh_fields()
				}
			});
		}
	},
});
