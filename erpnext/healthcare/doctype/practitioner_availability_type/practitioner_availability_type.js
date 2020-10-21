// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Practitioner Availability Type', {
	refresh: function(frm) {

	},
	appointment_type: function(frm) {
		if(frm.doc.appointment_type){
			frappe.db.get_value('Appointment Type', {name: frm.doc.appointment_type}, ['default_duration', 'color'], (r) => {
				if(r.color){
					frm.set_value("color", r.color);
				}
				if(r.default_duration){
					frm.set_value("duration", r.default_duration);
				}
			});
		}
	}
});
