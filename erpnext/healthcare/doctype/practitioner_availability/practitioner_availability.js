// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Practitioner Availability', {
	refresh: function(frm) {
		set_event_type_properties_to_event(frm);
		frm.set_query('service_unit', function(){
			return {
				filters: {
					'is_group': false,
					'allow_appointments': true
				}
			};
		});
	},
	from_date: function(frm) {
		if(frm.doc.from_date){
			frm.set_value('to_date', frm.doc.from_date);
		}
	},
	service_unit: function(frm){
		if(frm.doc.service_unit){
			frappe.db.get_value('Healthcare Service Unit', {name: frm.doc.service_unit}, 'total_service_unit_capacity', (r) => {
				if(r.total_service_unit_capacity && r.total_service_unit_capacity>0){
					frm.set_df_property('total_service_unit_capacity', 'hidden', 0);
					frm.set_df_property('appointment_type', 'reqd', 1);
					frm.set_df_property('duration', 'reqd', 1);
					frm.set_value('total_service_unit_capacity', r.total_service_unit_capacity);
					var desp_str='Maximum Capacity '+ r.total_service_unit_capacity
					frm.set_df_property('total_service_unit_capacity', 'description', desp_str);
				}
				else{
					frm.set_df_property('total_service_unit_capacity', 'hidden', 1);
					frm.set_value('total_service_unit_capacity', '');
					frm.set_df_property('appointment_type', 'reqd', 0);
					frm.set_df_property('duration', 'reqd', 0);
				}
			});
		}
	},
	total_service_unit_capacity: function(frm){
		frappe.db.get_value('Healthcare Service Unit', {name: frm.doc.service_unit}, 'total_service_unit_capacity', (r) => {
			if(r.total_service_unit_capacity){
				if (r.total_service_unit_capacity<frm.doc.total_service_unit_capacity){
					frappe.show_alert({message:__('Not Allowed'), indicator:'red'});
					frm.get_field('total_service_unit_capacity').$input.select();
				}
			}
		});
	},
	availability_type: function(frm) {
		set_event_type_properties_to_event(frm);
	},
	appointment_type: function(frm) {
		if(frm.doc.appointment_type){
			frappe.db.get_value('Appointment Type', {name: frm.doc.appointment_type}, 'default_duration', (r) => {
				if(r.default_duration){
					frm.set_value('duration', r.default_duration);
				}
			});
		}
	},
	repeat_on: function(frm) {
		if(frm.doc.repeat_on==='Every Day') {
			['monday', 'tuesday', 'wednesday', 'thursday',
				'friday', 'saturday', 'sunday'].map(function(v) {
					frm.set_value(v, 1);
				});
		}
	}
});

var set_event_type_properties_to_event = function(frm){
	if(frm.doc.availability_type){
		frappe.db.get_value('Practitioner Availability Type', {name: frm.doc.availability_type}, ['availability_name','present','appointment_type','color', 'duration'], (r) =>{
			frm.set_value('present', r.present);
			frm.set_df_property('present', 'read_only', 1);
			frm.set_value('availability', r.availability_name);
			frm.set_df_property('availability', 'read_only', 1);
			if(r.appointment_type){
				frm.set_value('appointment_type', r.appointment_type);
				frm.set_df_property('appointment_type', 'read_only', 1);
			}
			if(r.color){
				frm.set_value('color', r.color);
				frm.set_df_property('color', 'read_only', 1);
			}
			if(r.default_duration){
				frm.set_value('duration', r.default_duration);
				frm.set_df_property('duration', 'read_only', 1);
			}
		});
	}
	else{
		frm.set_df_property('present', 'read_only', 0);
		frm.set_df_property('availability', 'read_only', 0);
		frm.set_df_property('appointment_type', 'read_only', 0);
		frm.set_df_property('color', 'read_only', 0);
			if(!frm.doc.total_service_unit_capacity && !frm.doc.total_service_unit_capacity>0){
				frm.set_df_property('duration', 'read_only', 0);
			}
			else{
				frm.set_df_property('duration', 'read_only', 1);
			}
	}
}
