// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Insurance Coverage', {
	refresh: function(frm) {

	},

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
