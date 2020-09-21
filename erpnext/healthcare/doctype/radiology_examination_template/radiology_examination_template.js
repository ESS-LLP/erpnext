    // Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Radiology Examination Template', {
	procedure_name: function (frm) {
		if (!frm.doc.item_code)
			frm.set_value("item_code", frm.doc.procedure_name);
		if (!frm.doc.description)
			frm.set_value("description", frm.doc.procedure_name);
	},
});
