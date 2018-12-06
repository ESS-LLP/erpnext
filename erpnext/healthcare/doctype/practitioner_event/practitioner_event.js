// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Practitioner Event', {
	from_date: function(frm) {
		if(frm.doc.from_date){
			frm.set_value("to_date", frm.doc.from_date);
		}
	},
	appointment_type: function(frm) {
		if(frm.doc.appointment_type){
			frappe.db.get_value('Appointment Type', {name: frm.doc.appointment_type}, 'default_duration', (r) => {
				if(r.default_duration){
					frm.set_value("duration", r.default_duration);
				}
			});
		}
	}
});
