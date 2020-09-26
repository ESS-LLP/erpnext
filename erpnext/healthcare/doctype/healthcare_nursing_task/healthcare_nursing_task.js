// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Healthcare Nursing Task', {
	refresh: function(frm) {
		frm.set_query("service_unit", function(){
				return {
					filters: {
						"is_group": false
					}
				};
			});
		}
});
