// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Insurance Assignment', {
	refresh: function(frm) {

	},
	patient: function(frm){
		if(frm.doc.patient){
			frappe.call({
				"method": "frappe.client.get",
				args: {
					doctype: "Patient",
					name: frm.doc.patient
				},
				callback: function (data) {
					frm.set_value("patient_name", data.message.patient_name);
					frm.set_value("gender", data.message.sex);
					frm.set_value("mobile_number", data.message.mobile);
					if(data.message.dob){
						$(frm.fields_dict['age_html'].wrapper).html("AGE : " + get_age(data.message.dob));
					}
					frm.refresh_fields()
				}
			});
		}
	}
});
var get_age = function (birth) {
	var ageMS = Date.parse(Date()) - Date.parse(birth);
	var age = new Date();
	age.setTime(ageMS);
	var years = age.getFullYear() - 1970;
	return years + " Year(s) " + age.getMonth() + " Month(s) " + age.getDate() + " Day(s)";
};
