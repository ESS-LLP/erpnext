// Copyright (c) 2016, ESS LLP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Healthcare Practitioner', {
	setup: function(frm) {
		frm.set_query('account', 'accounts', function(doc, cdt, cdn) {
			var d	= locals[cdt][cdn];
			return {
				filters: {
					'root_type': 'Income',
					'company': d.company,
					'is_group': 0
				}
			};
		});
	},
	refresh: function(frm) {
		frappe.dynamic_link = {doc: frm.doc, fieldname: 'name', doctype: 'Healthcare Practitioner'};
		if(!frm.is_new()) {
			frappe.contacts.render_address_and_contact(frm);
		}
		frm.set_query("service_unit", "practitioner_schedules", function(){
			return {
				filters: {
					"is_group": false,
					"allow_appointments": true
				}
			};
		});
		if(frm.doc.department){
			frm.set_query("practitioner_service_profile", function () {
				return {
					filters: {healthcare_practitioner_type : frm.doc.healthcare_practitioner_type}
				}
			});
		}
		manage_internal_external_practitioner(frm);
		set_query_service_item(frm, 'inpatient_visit_charge_item');
		set_query_service_item(frm, 'op_consulting_charge_item');
	},
	practitioner_service_profile: function(frm) {
		frm.clear_table("appointment_types");
		frm.clear_table("clinical_procedures");
		frm.clear_table("revenue_sharing_items");
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
						if(r.message.clinical_procedures){
							var clinical_procedure_templates = r.message.clinical_procedures;
							clinical_procedure_templates.forEach(function(template) {
								var template_item = frappe.model.add_child(frm.doc, 'Service Profile Clinical Procedures', 'clinical_procedures');
								frappe.model.set_value(template_item.doctype, template_item.name, 'clinical_procedure_template', template.clinical_procedure_template)
							});
						}
						if(r.message.revenue_sharing_items){
							var revenue_sharing = r.message.revenue_sharing_items;
							revenue_sharing.forEach(function(item) {
								var revenue_sharing_item = frappe.model.add_child(frm.doc, 'Service Profile Item Groups', 'revenue_sharing_items');
								frappe.model.set_value(revenue_sharing_item.doctype, revenue_sharing_item.name, 'item_group', item.item_group)
								frappe.model.set_value(revenue_sharing_item.doctype, revenue_sharing_item.name, 'type_of_sharing', item.type_of_sharing)
								if(item.type_of_sharing == "Fixed"){
									frappe.model.set_value(revenue_sharing_item.doctype, revenue_sharing_item.name, 'direct_amount', item.direct_amount)
									frappe.model.set_value(revenue_sharing_item.doctype, revenue_sharing_item.name, 'referral_amount', item.referral_amount)
								}
								else if(item.type_of_sharing == "Percentage"){
									frappe.model.set_value(revenue_sharing_item.doctype, revenue_sharing_item.name, 'direct_percentage', item.direct_percentage)
									frappe.model.set_value(revenue_sharing_item.doctype, revenue_sharing_item.name, 'referral_percentage', item.referral_percentage)
								}
							});
						}
						refresh_field("appointment_types");
						refresh_field("clinical_procedures");
						refresh_field("revenue_sharing_items")
					}
				}
			});
		}
	},
	healthcare_practitioner_type: function(frm) {
		manage_internal_external_practitioner(frm);
	},
	supplier: function(frm) {
		if(frm.doc.supplier){
			frappe.call({
				"method": "frappe.client.get",
				args: {
					doctype: "Supplier",
					name: frm.doc.supplier
				},
				callback: function (data) {
					if(!frm.doc.first_name || !frm.doc.user_id){
						frappe.model.set_value(frm.doctype,frm.docname, "first_name", data.message.supplier_name);
					}
				}
			});
		}
	}
});

var set_query_service_item = function(frm, service_item_field) {
	frm.set_query(service_item_field, function() {
		return {
			filters: {
				'is_sales_item': 1,
				'is_stock_item': 0
			}
		};
	});
};

var manage_internal_external_practitioner = function(frm) {
	frm.set_df_property("employee", "reqd", 0);
	frm.set_df_property("employee", "hidden", 1);
	frm.set_df_property("supplier", "reqd", 0);
	frm.set_df_property("supplier", "hidden", 1);
	if(frm.doc.healthcare_practitioner_type){
		if(frm.doc.healthcare_practitioner_type == "Internal"){
			frm.set_df_property("employee", "hidden", 0);
			frm.set_df_property("employee", "reqd", 1);
		}
		else if(frm.doc.healthcare_practitioner_type == "External"){
			frm.set_df_property("supplier", "hidden", 0);
			frm.set_df_property("supplier", "reqd", 1);
		}
	}
}

frappe.ui.form.on("Healthcare Practitioner", "user_id",function(frm) {
	if(frm.doc.user_id){
		frappe.call({
			"method": "frappe.client.get",
			args: {
				doctype: "User",
				name: frm.doc.user_id
			},
			callback: function (data) {

				frappe.model.get_value('Employee', {'user_id': frm.doc.user_id}, 'name',
					function(data) {
						if(data){
							if(!frm.doc.employee || frm.doc.employee != data.name)
								frappe.model.set_value(frm.doctype,frm.docname, "employee", data.name);
						}else{
							frappe.model.set_value(frm.doctype,frm.docname, "employee", "");
						}
					}
				);

				if(!frm.doc.first_name || frm.doc.first_name != data.message.first_name)
					frappe.model.set_value(frm.doctype,frm.docname, "first_name", data.message.first_name);
				if(!frm.doc.middle_name || frm.doc.middle_name != data.message.middle_name)
					frappe.model.set_value(frm.doctype,frm.docname, "middle_name", data.message.middle_name);
				if(!frm.doc.last_name || frm.doc.last_name != data.message.last_name)
					frappe.model.set_value(frm.doctype,frm.docname, "last_name", data.message.last_name);
				if(!frm.doc.mobile_phone || frm.doc.mobile_phone != data.message.mobile_no)
					frappe.model.set_value(frm.doctype,frm.docname, "mobile_phone", data.message.mobile_no);
			}
		});
	}
});

frappe.ui.form.on("Healthcare Practitioner", "employee", function(frm) {
	if(frm.doc.employee){
		frappe.call({
			"method": "frappe.client.get",
			args: {
				doctype: "Employee",
				name: frm.doc.employee
			},
			callback: function (data) {
				if(!frm.doc.user_id || frm.doc.user_id != data.message.user_id)
					frm.set_value("user_id", data.message.user_id);
				if(!frm.doc.designation || frm.doc.designation != data.message.designation)
					frappe.model.set_value(frm.doctype,frm.docname, "designation", data.message.designation);
				if(!frm.doc.first_name || !frm.doc.user_id){
					frappe.model.set_value(frm.doctype,frm.docname, "first_name", data.message.first_name);
					frappe.model.set_value(frm.doctype,frm.docname, "middle_name", data.message.middle_name);
					frappe.model.set_value(frm.doctype,frm.docname, "last_name", data.message.last_name);
				}
				if(!frm.doc.mobile_phone || !frm.doc.user_id)
					frappe.model.set_value(frm.doctype,frm.docname, "mobile_phone", data.message.cell_number);
				if(!frm.doc.address || frm.doc.address != data.message.current_address)
					frappe.model.set_value(frm.doctype,frm.docname, "address", data.message.current_address);
			}
		});
	}
});
