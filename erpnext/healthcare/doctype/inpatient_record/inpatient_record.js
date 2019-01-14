// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Inpatient Record', {
	setup: function(frm) {
		frm.get_field('drug_prescription').grid.editable_fields = [
			{fieldname: 'drug_code', columns: 2},
			{fieldname: 'drug_name', columns: 2},
			{fieldname: 'dosage', columns: 2},
			{fieldname: 'period', columns: 2}
		];
	},
	refresh: function(frm) {
		if(!frm.doc.__islocal && frm.doc.status == "Admission Scheduled"){
			frm.add_custom_button(__('Admit'), function() {
				admit_patient_dialog(frm);
			} );
			frm.set_df_property("btn_transfer", "hidden", 1);
		}
		if(!frm.doc.__islocal && frm.doc.status == "Discharge Scheduled"){
			frm.add_custom_button(__('Discharge'), function() {
				discharge_patient(frm);
			} );
			frm.set_df_property("btn_transfer", "hidden", 0);
		}
		if(!frm.doc.__islocal && (frm.doc.status == "Discharged" || frm.doc.status == "Discharge Scheduled")){
			frm.disable_save();
			frm.set_df_property("btn_transfer", "hidden", 1);
		}
		if(!frm.doc.__islocal && frm.doc.drug_prescription){
			show_table_html(frm, frm.doc.drug_prescription, "drug_prescription", frm.fields_dict.drug_prescription_html)
		}
		if(!frm.doc.__islocal && frm.doc.lab_test_prescription){
			show_table_html(frm, frm.doc.lab_test_prescription, "lab_test_prescription", frm.fields_dict.lab_test_prescription_html)
		}
		if(!frm.doc.__islocal && frm.doc.procedure_prescription){
			show_table_html(frm, frm.doc.procedure_prescription, "procedure_prescription", frm.fields_dict.procedure_prescription_html)
		}
	},
	btn_transfer: function(frm) {
		transfer_patient_dialog(frm);
	}
});

var discharge_patient = function(frm) {
	frappe.call({
		doc: frm.doc,
		method: "discharge",
		callback: function(data) {
			if(!data.exc){
				frm.reload_doc();
			}
		},
		freeze: true,
		freeze_message: "Process Discharge"
	});
};

var admit_patient_dialog = function(frm){
	var dialog = new frappe.ui.Dialog({
		title: 'Admit Patient',
		width: 100,
		fields: [
			{fieldtype: "Link", label: "Service Unit Type", fieldname: "service_unit_type", options: "Healthcare Service Unit Type"},
			{fieldtype: "Link", label: "Service Unit", fieldname: "service_unit", options: "Healthcare Service Unit", reqd: 1},
			{fieldtype: "Datetime", label: "Admission Datetime", fieldname: "check_in", reqd: 1},
			{fieldtype: "Date", label: "Expected Discharge", fieldname: "expected_discharge"}
		],
		primary_action_label: __("Admit"),
		primary_action : function(){
			var service_unit = dialog.get_value('service_unit');
			var check_in = dialog.get_value('check_in');
			var expected_discharge = null;
			if(dialog.get_value('expected_discharge')){
				expected_discharge = dialog.get_value('expected_discharge');
			}
			if(!service_unit && !check_in){
				return;
			}
			frappe.call({
				doc: frm.doc,
				method: 'admit',
				args:{
					'service_unit': service_unit,
					'check_in': check_in,
					'expected_discharge': expected_discharge
				},
				callback: function(data) {
					if(!data.exc){
						frm.reload_doc();
					}
				},
				freeze: true,
				freeze_message: "Process Admission"
			});
			frm.refresh_fields();
			dialog.hide();
		}
	});

	dialog.fields_dict["check_in"].df.onchange = () => {
		if(dialog.get_value('check_in')){
			if (frm.doc.expected_length_of_stay && frm.doc.expected_length_of_stay > 0){
				dialog.set_values({
					'expected_discharge': frappe.datetime.add_days(dialog.get_value('check_in'), frm.doc.expected_length_of_stay)
				});
			}
		}
		else{
			dialog.set_values({
				'expected_discharge': ""
			});
		}
	}

	dialog.fields_dict["service_unit_type"].get_query = function(){
		return {
			filters: {
				"inpatient_occupancy": 1,
				"allow_appointments": 0
			}
		};
	};
	dialog.fields_dict["service_unit"].get_query = function(){
		return {
			filters: {
				"is_group": 0,
				"service_unit_type": dialog.get_value("service_unit_type"),
				"occupancy_status" : "Vacant"
			}
		};
	};

	var check_in_date_time = frappe.datetime.now_datetime();
	var expected_discharge_date = "";

	if(frm.doc.admission_ordered_for){
		check_in_date_time = frm.doc.admission_ordered_for+" "+frappe.datetime.now_time();
		if (frm.doc.expected_length_of_stay && frm.doc.expected_length_of_stay > 0){
			expected_discharge_date = frappe.datetime.add_days(frm.doc.admission_ordered_for, frm.doc.expected_length_of_stay);
		}
	}

	dialog.set_values({
		'service_unit_type': frm.doc.admission_service_unit_type,
		'check_in': check_in_date_time,
		'expected_discharge': expected_discharge_date
	});

	dialog.show();
};

var transfer_patient_dialog = function(frm){
	var dialog = new frappe.ui.Dialog({
		title: 'Transfer Patient',
		width: 100,
		fields: [
			{fieldtype: "Link", label: "Leave From", fieldname: "leave_from", options: "Healthcare Service Unit", reqd: 1, read_only:1},
			{fieldtype: "Link", label: "Service Unit Type", fieldname: "service_unit_type", options: "Healthcare Service Unit Type"},
			{fieldtype: "Link", label: "Transfer To", fieldname: "service_unit", options: "Healthcare Service Unit", reqd: 1},
			{fieldtype: "Datetime", label: "Check In", fieldname: "check_in", reqd: 1}
		],
		primary_action_label: __("Transfer"),
		primary_action : function(){
			var service_unit = null;
			var check_in = dialog.get_value('check_in');
			var leave_from = null;
			if(dialog.get_value('leave_from')){
				leave_from = dialog.get_value('leave_from');
			}
			if(dialog.get_value('service_unit')){
				service_unit = dialog.get_value('service_unit');
			}
			if(!check_in){
				return;
			}
			frappe.call({
				doc: frm.doc,
				method: 'transfer',
				args:{
					'service_unit': service_unit,
					'check_in': check_in,
					'leave_from': leave_from
				},
				callback: function(data) {
					if(!data.exc){
						frm.reload_doc();
					}
				},
				freeze: true,
				freeze_message: "Process Transfer"
			});
			frm.refresh_fields();
			dialog.hide();
		}
	});

	dialog.fields_dict["leave_from"].get_query = function(){
		return {
			query : "erpnext.healthcare.doctype.inpatient_record.inpatient_record.get_leave_from",
			filters: {docname:frm.doc.name}
		};
	};
	dialog.fields_dict["service_unit_type"].get_query = function(){
		return {
			filters: {
				"inpatient_occupancy": 1,
				"allow_appointments": 0
			}
		};
	};
	dialog.fields_dict["service_unit"].get_query = function(){
		return {
			filters: {
				"is_group": 0,
				"service_unit_type": dialog.get_value("service_unit_type"),
				"occupancy_status" : "Vacant"
			}
		};
	};

	dialog.show();

	var not_left_service_unit = null;
	for(let inpatient_occupancy in frm.doc.inpatient_occupancies){
		if(frm.doc.inpatient_occupancies[inpatient_occupancy].left != 1){
			not_left_service_unit = frm.doc.inpatient_occupancies[inpatient_occupancy].service_unit;
		}
	}
	dialog.set_values({
		'leave_from': not_left_service_unit
	});
};

var show_table_html = function(frm, child_table, child_table_name, html_field) {
	setTimeout(function() {
		var $wrapper = html_field.$wrapper;
		var table_html = "<div class='col-md-12 col-sm-12 text-muted'>";
		var table_head = null;
		var table_row = null;
		var table_fields = frm.get_field(child_table_name).grid.docfields;
		var abcd = frm.get_field(child_table_name).grid

		table_head = '<tr>'
		$.each(table_fields, function(i, table_field) {
			if(table_field.in_list_view == 1){
				table_head = table_head + '<th>' + table_field.label + '</th>'
			}
		});
		table_head = table_head + '</tr>'

		$.each(child_table, function(index, data_object){
			var procedure_comment = "";
			if(table_row == null){
				table_row = '<tr>'
			}
			else{
				table_row = table_row + '<tr>'
			}
			$.each(table_fields, function(i, table_field) {
				if(table_field.in_list_view == 1){
					table_row = table_row + '<td>'+data_object[table_field.fieldname]+'</td>'
				}
			});
			table_row = table_row + '</tr>'
		});

		table_html = table_html + '<table class="table table-condensed \
			bordered">' + table_head +  table_row + '</table> <br/> <hr/>' + "</div>"
		$wrapper
			.css('margin-bottom', 0)
			.html(table_html);
	}, 1000)
}
