// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Insurance Contract', {
	refresh: function(frm) {
		frm.set_query("price_list", function() {
			return {
				filters: {
					'selling':1
				}
			};
		});
		if(frm.is_new){
			frm.set_value("start_date", frappe.datetime.get_today())
		}
	},
	start_date: function(frm){
		var to_date=frappe.datetime.add_days(frm.doc.start_date, 365)
		frm.set_value("end_date", to_date);
	}
});
