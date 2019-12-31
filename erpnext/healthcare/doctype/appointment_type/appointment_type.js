// Copyright (c) 2016, ESS LLP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Appointment Type', {
	onload:function(frm){
		frm.set_query('medical_code', () => {
    return {
        filters: {
            medical_code_standard: frm.doc.medical_code_standard
        }
    }
})
	},
});
