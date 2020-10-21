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
			if(!frm.doc.__islocal){
				frm.add_custom_button(__('Completed'), function() {
					make_status_completed(frm);
				});
			}
		},
		make_status_completed: function (frm) {
			frm.set_value('status', 'Completed');
		}
});
