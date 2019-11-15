// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Healthcare Service Profile Assignment', {
	refresh: function(frm) {
	},
	practitioner_service_profile: function(frm) {
		if(frm.doc.practitioner_service_profile){
			frappe.call({
				method: "frappe.client.get",
				args : {doctype: "Practitioner Service Profile", name: frm.doc.practitioner_service_profile},
				callback: function(r){
					if(r.message){
						if(r.message.appointment_types){
							var appointment_types = r.message.appointment_types;
							appointment_types.forEach(function(appt) {
								var appointment_type_item = frappe.model.add_child(frm.doc, 'Service Profile Appointment Type', 'appointment_types');
								frappe.model.set_value(appointment_type_item.doctype, appointment_type_item.name, 'appointment_type', appt.appointment_type)
							});
						}
						if(r.message.clinical_procedure_templates){
							var clinical_procedure_templates = r.message.clinical_procedure_templates;
							clinical_procedure_templates.forEach(function(template) {
								var template_item = frappe.model.add_child(frm.doc, 'Service Profile Procedure Template', 'clinical_procedure_templates');
								frappe.model.set_value(template_item.doctype, template_item.name, 'clinical_procedure_template', template.clinical_procedure_template)
							});
						}
						refresh_field("appointment_types");
						refresh_field("clinical_procedure_templates");
					}
				}
			});
		}
	}
});
