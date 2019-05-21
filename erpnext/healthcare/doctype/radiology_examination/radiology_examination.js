// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Radiology Examination', {
	appointment: function(frm){
			frappe.call({
				"method": "frappe.client.get",
				args:{
					doctype:"Patient Appointment",
					name:frm.doc.appointment
				},
				callback: function(data){
					var patient_details_html = "";
					patient_details_html += "Patient ID : " + data.message.name + "<br/>"
					patient_details_html += "Name : " + data.message.patient_name + "<br/>"
					patient_details_html += "Appointment Type : " + data.message.appointment_type + "<br/>"
					patient_details_html += "Practitioner : " + data.message.practitioner + "<br/>"
					patient_details_html += "Department : " + data.message.department + "<br/>"
					patient_details_html += "Source: " + data.message.source + "<br/>"
					frm.fields_dict.patient_details_html.html(patient_details_html);
				}
			});
	},
	patient: function(frm){
		if(!frm.doc.appointment){
			frappe.call({
				"method": "frappe.client.get",
				args:{
					doctype:"Patient",
					name:frm.doc.patient
				},
				callback: function(data){
					var patient_details_html = "";
					patient_details_html += "Patient ID : " + data.message.name + "<br/>"
					patient_details_html += "Name : " + data.message.patient_name + "<br/>"
					patient_details_html += "Date Of Birth : " + data.message.dob + "<br/>"
					patient_details_html += "Gender : " + data.message.sex + "<br/>"
					patient_details_html += "Mobile : " + data.message.mobile + "<br/>"
					patient_details_html += "Email ID: " + data.message.email + "<br/>"
					frm.fields_dict.patient_details_html.html(patient_details_html);
				}
			});
		}
	}
});
