// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Radiology Examination', {
	appointment: function(frm){
			frappe.call({
				"method": "frappe.client.get",
				args:{
					doctype:"Patient Appointment",
					name:frm.doc.appointment
				},
				callback: function(data){
					if(data.message && data.message.name){
						var appointment = data.message;
						var patient_details_html = "";
						patient_details_html += "Patient : " + appointment.patient + "<br/>"
						patient_details_html += "Patient Name : " + appointment.patient_name + "<br/>"
						patient_details_html += "Appointment Type : " + appointment.appointment_type + "<br/>"
						patient_details_html += "Practitioner : " + appointment.practitioner + "<br/>"
						patient_details_html += "Department : " + appointment.department
						frm.fields_dict.appointment_details_html.html(patient_details_html);
						frm.set_value("patient", appointment.patient);
						frm.set_value("patient_name", appointment.patient_name);
						frm.set_value( "source", data.message.source);
						frm.set_value( "referring_practitioner", appointment.referring_practitioner);
						frm.set_df_property("patient", "hidden", 1);
						frm.set_df_property("patient_name", "hidden", 1);
					}
					else{
						frm.set_df_property("patient", "hidden", 0);
						frm.set_df_property("patient_name", "hidden", 0);
						frm.set_df_property("source", "read_only", 0);
						frm.set_value("patient", "");
						frm.set_value("patient_name", "");
						frm.set_value("source", "");
						frm.set_value("referring_practitioner", "");
						frm.fields_dict.appointment_details_html.html("");
					}
					if(data.message.insurance){
						frm.set_value("insurance", data.message.insurance)
						frm.set_df_property("insurance", "read_only", 1);
					}
				}
			});
	},
	patient: function(frm){
		if(frm.doc.patient){
			frappe.call({
				"method": "frappe.client.get",
				args:{
					doctype:"Patient",
					name:frm.doc.patient
				},
				callback: function(data){
					if(data.message){
						var patient = data.message;
						var patient_details_html = "";
						patient_details_html += patient.inpatient_record ?("Inpatient Record : " + patient.inpatient_record + "<br/>"):'';
						patient_details_html += patient.dob ?("Date Of Birth : " + patient.dob + "<br/>"):'';
						patient_details_html += patient.sex ?("Gender : " + patient.sex + "<br/>"):'';
						patient_details_html += patient.mobile ?("Mobile : " + patient.mobile + "<br/>"):'';
						patient_details_html += patient.email ?("Email ID: " + patient.email + "<br/>"):'';
						frm.fields_dict.patient_details_html.html(patient_details_html);
						if(patient.inpatient_record){
							frm.set_value("inpatient_record", patient.inpatient_record);
							frm.set_df_property("inpatient_record", "hidden", 1);
						}
					}
				}
			});
		}
		else{
			frm.fields_dict.patient_details_html.html("");
			frm.set_value("patient_name", "");
			frm.set_value("source", "");
			frm.set_value("referring_practitioner", "");
			frm.set_df_property("source", "read_only", 0);
		}
	},
	inpatient_record:function(frm) {
		if(frm.doc.inpatient_record){
			frappe.call({
				method: "frappe.client.get",
				args: {
					doctype: "Inpatient Record",
					name: frm.doc.inpatient_record
				},
				callback: function(r) {
					if(r.message){
						if(r.message.source){
							frm.set_value("source",r.message.source);
							frm.set_df_property("source", "read_only", 1);
						}
						else {
							frm.set_value("source", "");
							frm.set_df_property("source", "read_only", 0);
						}
						if(r.message.referring_practitioner){
							frm.set_value("referring_practitioner", r.message.referring_practitioner);
							frm.set_df_property("referring_practitioner", "read_only", 1);
						}
						else{
							frm.set_value("referring_practitioner", "");
							frm.set_df_property("referring_practitioner", "read_only", 0);
						}
						if(r.message.insurance){
							frm.set_value("insurance", r.message.insurance)
							frm.set_df_property("insurance", "read_only", 1);
						}
						else{
							frm.set_value("insurance", "")
							frm.set_df_property("insurance", "read_only", 0);
						}
					}
				}
			});
		}
	},
	source: function(frm){
		if(frm.doc.source=="Direct"){
			frm.set_value("referring_practitioner", "");
			frm.set_df_property("referring_practitioner", "hidden", 1);
		}else if(frm.doc.source=="Referral"){
			if(frm.doc.referring_practitioner==""){
				if(frm.doc.practitioner){
					frm.set_value("referring_practitioner", frm.doc.practitioner);
					frm.set_df_property("referring_practitioner", "hidden", 0);
					frm.set_df_property("referring_practitioner", "read_only", 1);
					frm.set_df_property("referring_practitioner", "reqd", 1);
				}
				else{
					frm.set_df_property("referring_practitioner", "read_only", 0);
					frm.set_df_property("referring_practitioner", "hidden", 0);
					frm.set_df_property("referring_practitioner", "reqd", 1);
				}
			}
			else{
				frm.set_df_property("source", "read_only", 1);
				frm.set_df_property("referring_practitioner", "hidden", 0);
				frm.set_df_property("referring_practitioner", "read_only", 1);
				frm.set_df_property("referring_practitioner", "reqd", 1);
			}
		}else if(frm.doc.source=="External Referral"){
			if(!frm.doc.referring_practitioner){
				frm.set_df_property("referring_practitioner", "read_only", 0);
				frm.set_df_property("referring_practitioner", "hidden", 0);
				frm.set_df_property("referring_practitioner", "reqd", 1);
			}
			else{
				frm.set_df_property("referring_practitioner", "read_only", 1);
				frm.set_df_property("referring_practitioner", "hidden", 0);
				frm.set_df_property("referring_practitioner", "reqd", 1);
			}
		}
	},
	refresh :  function(frm){
		if(frm.doc.__islocal){
			frm.add_custom_button(__('Get from Patient Encounter'), function () {
				get_radiology_procedure_prescribed(frm);
			});
		}
		if(frm.doc.appointment ){
			frm.set_df_property("patient", "read_only", 1);
		}
		else
		{
			frm.set_df_property("patient", "read_only", 0);
			refresh_field("patient");
		}
		frm.set_query("service_unit", function(){
			return {
				filters: {
					"is_group": false
				}
			};
		});
		frm.set_query("insurance", function(){
			return {
				filters: {
					"patient": frm.doc.patient
				}
			};
		});
	}
});
var get_radiology_procedure_prescribed = function(frm){
	if(frm.doc.patient){
		frappe.call({
			method:	"erpnext.healthcare.doctype.radiology_examination.radiology_examination.get_radiology_procedure_prescribed",
			args:	{patient: frm.doc.patient},
			callback: function(r){
				show_radiology_procedure(frm, r.message);
			}
		});
	}
	else{
		frappe.msgprint(__("Please select Patient to Radiology Procedure"));
	}
};

var show_radiology_procedure = function(frm, result){
	var d = new frappe.ui.Dialog({
		title: __("Radiology Procedure Prescriptions"),
		fields: [
			{
				fieldtype: "HTML", fieldname: "radiology_prescribed"
			}
		]
	});
	var html_field = d.fields_dict.radiology_prescribed.$wrapper;
	html_field.empty();
	$.each(result, function(x, y){
		var row = $(repl('<div class="col-xs-12" style="padding-top:12px; text-align:center;" >\
		<div class="col-xs-2"> %(radiology_procedure)s </div>\
		<div class="col-xs-2"> %(encounter)s </div>\
		<div class="col-xs-3"> %(date)s </div>\
		<div class="col-xs-1">\
		<a data-name="%(name)s" data-radiology-procedure="%(radiology_procedure)s"\
		data-encounter="%(encounter)s"\
		data-invoiced="%(invoiced)s" data-source="%(source)s" data-referring-practitioner="%(referring_practitioner)s" \
		data-insurance="%(insurance)s" href="#"><button class="btn btn-default btn-xs">Get Radiology\
		</button></a></div></div>', {name:y[0], radiology_procedure: y[1], encounter:y[2], invoiced:y[3],  date:y[4], source:y[5],
		referring_practitioner:y[6], insurance:y[8]? y[8]:''})).appendTo(html_field);
		row.find("a").click(function() {
			frm.doc.radiology_procedure = $(this).attr("data-radiology-procedure");
			frm.set_df_property("patient", "read_only", 1);
			frm.doc.invoiced = 0;
			if($(this).attr("data-invoiced") == 1){
				frm.doc.invoiced = 1;
			}
			frm.doc.source =  $(this).attr("data-source");
			frm.doc.referring_practitioner= $(this).attr("data-referring-practitioner")
			if(frm.doc.referring_practitioner){
				frm.set_df_property("referring_practitioner", "hidden", 0);
			}
			frm.doc.insurance = $(this).attr("data-insurance");
			if(frm.doc.insurance){
				frm.set_df_property("insurance", "read_only", 1);
			}
			refresh_field("source");
			refresh_field("referring_practitioner");
			refresh_field("invoiced");
			refresh_field("radiology_procedure");
			d.hide();
			return false;
		});
	});
	if(!result){
		var msg = "There are no Radiology prescribed for "+frm.doc.patient;
		$(repl('<div class="col-xs-12" style="padding-top:20px;" >%(msg)s</div></div>', {msg: msg})).appendTo(html_field);
	}
	d.show();
};
