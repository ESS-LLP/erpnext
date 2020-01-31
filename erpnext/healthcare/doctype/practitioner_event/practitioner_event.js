// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Practitioner Event', {
	refresh: function(frm) {
		frm.set_query("service_unit", function(){
			return {
				filters: {
					"is_group": false,
					"allow_appointments": true
				}
			};
		});
	},
	from_date: function(frm) {
		if(frm.doc.from_date){
			frm.set_value("to_date", frm.doc.from_date);
		}
	},
	service_unit: function(frm){
		if(frm.doc.service_unit){
			frappe.db.get_value('Healthcare Service Unit', {name: frm.doc.service_unit}, 'total_service_unit_capacity', (r) => {
				if(r.total_service_unit_capacity){
					frm.set_value("total_service_unit_capacity", r.total_service_unit_capacity);
					var desp_str='Maximum Capacity '+ r.total_service_unit_capacity
					frm.set_df_property("total_service_unit_capacity", "description", desp_str);
				}
			});
		}
	},
	total_service_unit_capacity: function(frm){
		frappe.db.get_value('Healthcare Service Unit', {name: frm.doc.service_unit}, 'total_service_unit_capacity', (r) => {
			if(r.total_service_unit_capacity){
				if (r.total_service_unit_capacity<frm.doc.total_service_unit_capacity){
					frappe.show_alert({message:__("Not Allowed"), indicator:'red'});
					frm.get_field("total_service_unit_capacity").$input.select();
				}
			}
		});
	},
	event_type: function(frm) {
		if(frm.doc.event_type){
			frappe.db.get_value('Practitioner Event Type', {name: frm.doc.event_type}, ['event_name','present','appointment_type','color', 'duration'], (r) =>{
				if(r.event_name){
					frm.set_value("event", r.event_name);
					frm.set_df_property("event", "read_only", 1);
				}
				if(r.present){
					frm.set_value("present", r.present);
					frm.set_df_property("present", "read_only", 1);
				}
				if(r.appointment_type){
					frm.set_value("appointment_type", r.appointment_type);
					frm.set_df_property("appointment_type", "read_only", 1);
				}
				if(r.color){
					frm.set_value("color", r.color);
					frm.set_df_property("color", "read_only", 1);
				}
				if(r.default_duration){
					frm.set_value("duration", r.default_duration);
					frm.set_df_property("duration", "read_only", 1);
				}
			});
		}
	},
	appointment_type: function(frm) {
		if(frm.doc.appointment_type){
			frappe.db.get_value('Appointment Type', {name: frm.doc.appointment_type}, ['default_duration', 'color'], (r) => {
				if(r.color){
					frm.set_value("color", r.color);
					frm.set_df_property("color", "read_only", 1);
				}
				if(r.default_duration){
					frm.set_value("duration", r.default_duration);
					frm.set_df_property("duration", "read_only", 1);
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
