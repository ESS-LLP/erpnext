// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Insurance Claim Submission', {
	refresh: function(frm){
		cur_frm.fields_dict["insurance_claim_submission_item"].grid.frm.$wrapper.find('.grid-add-row').hide();
		if(frm.doc.docstatus==1 && !frm.doc.__islocal){
			if(frm.doc.is_finished != 1){
				frm.add_custom_button(__("Complete"), function() {
					frm.events.update_final_claim_details(frm);
				});
			}
			else{
				frm.add_custom_button(__("Payment"), function() {
					frm.events.make_payment_entry(frm);
				});
			}
			cur_frm.fields_dict["insurance_claim_submission_item"].grid.frm.$wrapper.find('.grid-add-row').hide();
			if(frm.doc.is_finished != 1){
				cur_frm.fields_dict["insurance_claim_submission_item"].grid.add_custom_button(__('Claim Rejected'), () => {
					var rejectedcliam=cur_frm.fields_dict["insurance_claim_submission_item"].grid.get_selected_children()
					for (var i in rejectedcliam) {
						var item = rejectedcliam[i];
						frappe.model.set_value(item.doctype, item.name, "rejected_amount", item.insurance_claim_amount);
					}
					set_total_Claim_Amount(frm);
				});
				cur_frm.fields_dict["insurance_claim_submission_item"].grid.add_custom_button(__('Claim Approved'), () => {
					var approvedclaim=cur_frm.fields_dict["insurance_claim_submission_item"].grid.get_selected_children()
					for (var i in approvedclaim) {
						var item = approvedclaim[i];
						frappe.model.set_value(item.doctype, item.name, "approved_amount", item.insurance_claim_amount);
					}
					set_total_Claim_Amount(frm);
				});
			}
		}
		if(frm.doc.docstatus==0)
		{
			var df = frappe.meta.get_docfield("Insurance Claim Item", "claim_status", frm.doc.name);
			df.read_only = 1;
		}
	},
	from_date: function(frm){
		get_insurance_claim(frm);
	},
	to_date: function(frm){
		get_insurance_claim(frm);
	},
	insurance_company: function(frm){
		get_insurance_claim(frm);
	},
	make_payment_entry: function(frm) {
		return frappe.call({
			method: "create_payment_entry",
			doc: frm.doc,
			callback: function(r) {
				var doc = frappe.model.sync(r.message);
				frappe.set_route("Form", doc[0].doctype, doc[0].name);
			}
		});
	},
	update_final_claim_details: function(frm) {
		return frappe.call({
			doc: frm.doc,
			method: "complete",
			callback: function(r) {
				frappe.show_alert({message:__("Submission Completed"), indicator:'green'});
				frm.refresh_fields();
			}
		});
	},
});

frappe.ui.form.on('Insurance Claim Item', {
	insurance_claim_submission_item_remove: function(frm) {
		set_total_Claim_Amount(frm);
	},
	approved_amount:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if(d.insurance_claim_amount){
			var rejected_amount=d.insurance_claim_amount-d.approved_amount;
			frappe.model.set_value(cdt, cdn,"rejected_amount",rejected_amount);
			set_claim_status(cdt,cdn,rejected_amount);
			set_total_Claim_Amount(frm);
		}
	},
	rejected_amount:function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if(d.insurance_claim_amount){
			var approved_amount=d.insurance_claim_amount-d.rejected_amount;
			frappe.model.set_value(cdt, cdn,"approved_amount",approved_amount);
			set_claim_status(cdt,cdn,d.rejected_amount);
			set_total_Claim_Amount(frm);
		}
	}
});

var set_claim_status = function(cdt,cdn, rejected_amount){
	var item = frappe.get_doc(cdt, cdn);
	if(rejected_amount !=0){
		if(rejected_amount==item.insurance_claim_amount){
			frappe.model.set_value(cdt, cdn,"claim_status","Claim Rejected")
		}
		else{
			 frappe.model.set_value(cdt, cdn,"claim_status","Partial")
		}
	}
	else{
		frappe.model.set_value(cdt, cdn,"claim_status","Claim Approved")
	}
}

var get_insurance_claim = function(frm){
	frm.doc.insurance_claim_submission_item = [];
	set_total_Claim_Amount(frm);
	if(frm.doc.insurance_company){
		var args = {'insurance_company': frm.doc.insurance_company}
		if(frm.doc.from_date){
			args['from_date'] = frm.doc.from_date
		}
		if(frm.doc.to_date){
			args['to_date'] = frm.doc.to_date
		}
		frappe.call({
			"method": "erpnext.healthcare.doctype.insurance_claim_submission.insurance_claim_submission.get_claim_submission_item",
			args:args,
			callback: function (data) {
					var item_fields = ['sales_invoice' , 'patient', 'patient_name',  'insurance_company','insurance_assignment','date_of_service',
										'item_code','item_name','discount_percentage','insurance_company_name', 'discount_amount','rate','amount',
										'insurance_claim_coverage', 'insurance_claim_amount', 'claim_status', 'insurance_approval_number', 'insurance_remarks' ]
				data.message.forEach(function(claim){
					$.each(claim.insurance_claim_item, function(i, claim_item) {
						var child_item=frappe.model.add_child(frm.doc, "Insurance Claim Item", "insurance_claim_submission_item")
						$.each(claim_item, function(field, value) {
							if(item_fields.includes(field)){
								frappe.model.set_value(child_item.doctype, child_item.name, field, value);
							}
							if(field == 'parent'){
								frappe.model.set_value(child_item.doctype, child_item.name, 'insurance_claim', value);
							}
							if(field=='name'){
								frappe.model.set_value(child_item.doctype, child_item.name, 'insurance_claim_item', value);
							}
						});
					});
				});
				frm.refresh_fields();
				set_total_Claim_Amount(frm);
			}

		});
	}
	frm.refresh_fields();
}

var set_total_Claim_Amount = function(frm){
	var total_amount=0;
	var total_approved_amount=0;
	var total_rejected_amount=0;
	for (var i in frm.doc.insurance_claim_submission_item) {
		var item = frm.doc.insurance_claim_submission_item[i];
		if(item.insurance_claim_amount ){
			total_amount=total_amount+item.insurance_claim_amount
		}
		if(item.approved_amount){
			total_approved_amount=total_approved_amount+item.approved_amount
		}
		if(item.rejected_amount){
			total_rejected_amount=total_rejected_amount+item.rejected_amount
		}
	}
	frappe.model.set_value(frm.doc.doctype, frm.doc.name, "total_claim_amount", total_amount)
	frappe.model.set_value(frm.doc.doctype, frm.doc.name, "total_rejected_amount", total_rejected_amount)
	frappe.model.set_value(frm.doc.doctype, frm.doc.name, "total_approved_amount", total_approved_amount)
};
