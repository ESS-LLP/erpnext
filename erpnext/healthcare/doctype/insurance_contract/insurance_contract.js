// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Insurance Contract', {
	refresh: function(frm) {
		if(frm.doc.__islocal){
			frm.set_value('start_date', frappe.datetime.get_today())
		}
		frm.set_query('default_insurance_coverage', function() {
			return {
				filters: {
					'docstatus': 1
				}
			};
		});

	},
	start_date: function(frm){
		if(frm.doc.start_date){
			var to_date=frappe.datetime.add_days(frm.doc.start_date, 365)
			frm.set_value('end_date', to_date);
		}
	},
	default_insurance_coverage: function (frm) {
		if (frm.doc.default_insurance_coverage) {
			frappe.call({
				'method': 'frappe.client.get',
				args: {
					doctype: 'Insurance Coverage',
					name: frm.doc.default_insurance_coverage
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
frappe.ui.form.on('Service Insurance Coverage',{
	insurance_coverage_slab:function(frm, cdt, cdn){
		var d = locals[cdt][cdn];
		if(d.insurance_coverage_slab){
			frappe.db.get_value('Insurance Coverage Slab', d.insurance_coverage_slab, 'percentage', (r) => {
				if (r.percentage) {
					frappe.model.set_value(cdt, cdn,'coverage_percent', r.percentage);
				}
			});
		}
	}
});
