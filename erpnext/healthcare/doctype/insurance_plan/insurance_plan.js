// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Insurance Plan', {
	refresh: function(frm) {
		frm.set_query('insurance_coverage', function() {
			return {
				filters: {
					'docstatus': 1
				}
			};
		});
	},
	insurance_company: function(frm){
		if(frm.doc.insurance_company){
			frappe.call({
				'method': 'frappe.client.get_value',
				args: {
					doctype: 'Insurance Contract',
					filters: {
						'insurance_company': frm.doc.insurance_company,
						'is_active':1,
						'end_date':['>=', frappe.datetime.nowdate()],
						'docstatus':1
					},
					fieldname: ['name']
				},
				callback: function (data) {
					if(!data.message.name){
						frappe.msgprint(__('There is no valid contract with this Insurance Company {0}',[frm.doc.insurance_company]));
						frm.set_value('insurance_company', '');
					}
				}
			});
		}
	},
	insurance_coverage: function (frm) {
		if (frm.doc.insurance_coverage) {
			frappe.call({
				'method': 'frappe.client.get',
				args: {
					doctype: 'Insurance Coverage',
					name: frm.doc.insurance_coverage
				},
				callback: function(data) {
					frm.doc.service_insurance_coverage = [];
					$.each(data.message.service_insurance_coverage, function(_i, e) {
						let services = frm.add_child('service_insurance_coverage');
						services.healthcare_service_group = e.healthcare_service_group;
						services.healthcare_service_type = e.healthcare_service_type;
						services.healthcare_service_templates = e.healthcare_service_templates;
						services.healthcare_service = e.healthcare_service;
						services.insurance_coverage_slab = e.insurance_coverage_slab;
						services.rate = e.rate;
						services.coverage_percent = e.coverage_percent;
						services.discount = e.discount;
						services.maximum_number_of_claims = e.maximum_number_of_claims;
						services.allow_to_override = e.allow_to_override;
					});
					refresh_field('service_insurance_coverage');
				}
			});
		}
	}
});
