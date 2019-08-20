// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Insurance Assignment', {
	refresh: function(frm) {

	},
	insurance_company: function(frm){
		if(frm.doc.insurance_company){
			frappe.call({
				"method": "frappe.client.get_value",
				args: {
					doctype: "Insurance Contract",
					filters: {
						'insurance_company': frm.doc.insurance_company,
						'is_active':1,
						'docstatus':1
					},
					fieldname: ['discount']
				},
				callback: function (data) {
					if(data.message){
						frm.set_value("discount", data.message.discount);
						frm.set_df_property("discount", "read_only", 1);
					}
				}
			});
		}
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
	},
	plan_name: function(frm){
		if(frm.doc.plan_name){
			frappe.call({
				"method": "frappe.client.get",
				args: {
					doctype: "Insurance plan",
					name: frm.doc.plan_name
				},
				callback: function (data) {
					frm.set_value("coverage", data.message.coverage);
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
