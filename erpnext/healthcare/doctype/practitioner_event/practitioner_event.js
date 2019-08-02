// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Practitioner Event', {
	refresh: function(frm) {
		frm.set_query("service_unit", function(){
			return {
				filters: {
					"is_group": false
				}
			};
		});
	},
	from_date: function(frm) {
		if(frm.doc.from_date){
			frm.set_value("to_date", frm.doc.from_date);
		}
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
	},
	repeat_on: function(frm) {
		if(frm.doc.repeat_on==="Every Day") {
			["monday", "tuesday", "wednesday", "thursday",
				"friday", "saturday", "sunday"].map(function(v) {
					frm.set_value(v, 1);
				});
		}
	}
});
