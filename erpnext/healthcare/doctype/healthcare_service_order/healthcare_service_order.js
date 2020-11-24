// Copyright (c) 2020, earthians and contributors
// For license information, please see license.txt

frappe.ui.form.on('Healthcare Service Order', {
	refresh: function(frm) {
		frm.set_query('insurance_subscription', function(){
			return{
				filters:{
					'patient': frm.doc.patient,
					'docstatus': 1
				}
			};
		});
	}
});
