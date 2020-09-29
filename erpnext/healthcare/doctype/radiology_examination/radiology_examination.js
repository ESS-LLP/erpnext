// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Radiology Examination', {
	appointment: function (frm) {
		if (frm.doc.appointment) {
			frappe.call({
				'method': 'frappe.client.get',
				args: {
					doctype: 'Patient Appointment',
					name: frm.doc.appointment
				},
				callback: function (data) {
					if (data.message && data.message.name) {
						var appointment = data.message;
						var patient_details_html = '';
						patient_details_html += 'Patient : ' + appointment.patient + '<br/>'
						patient_details_html += 'Patient Name : ' + appointment.patient_name + '<br/>'
						patient_details_html += 'Appointment Type : ' + appointment.appointment_type + '<br/>'
						patient_details_html += 'Practitioner : ' + appointment.practitioner + '<br/>'
						patient_details_html += 'Department : ' + appointment.department
						frm.fields_dict.appointment_details_html.html(patient_details_html);
						frm.set_value('patient', appointment.patient);
						frm.set_value('patient_name', appointment.patient_name);
						frm.set_value('radiology_examination_template', data.message.radiology_examination_template,);
						frm.set_value('medical_department', data.message.department);
						frm.set_value('start_date', data.message.appointment_date);
						frm.set_value('start_time', data.message.appointment_time);
						frm.set_value('notes', data.message.notes);
						frm.set_value('service_unit', data.message.service_unit);
						frm.set_value('modality', data.message.modality);
						frm.set_df_property('patient', 'hidden', 1);
						frm.set_df_property('patient_name', 'hidden', 1);
					}
					else {
						frm.set_df_property('patient', 'hidden', 0);
						frm.set_df_property('patient_name', 'hidden', 0);
						frm.set_df_property('source', 'read_only', 0);
						frm.set_value('patient', '');
						frm.set_value('patient_name', '');
						frm.set_value('radiology_examination_template', '');
						frm.set_value('medical_department', '');
						frm.set_value('start_date', '');
						frm.set_value('start_time', '');
						frm.set_value('notes', '');
						frm.set_value('service_unit', '');
						frm.set_value('modality', '');
						frm.fields_dict.appointment_details_html.html('');
					}
				}
			});
		}
		else {
			frm.set_df_property('patient', 'hidden', 0);
			frm.set_df_property('patient_name', 'hidden', 0);
			frm.set_df_property('source', 'read_only', 0);
			frm.set_value('patient', '');
			frm.set_value('patient_name', '');
			frm.set_value('radiology_examination_template', '');
			frm.set_value('medical_department', '');
			frm.set_value('start_date', '');
			frm.set_value('start_time', '');
			frm.set_value('notes', '');
			frm.set_value('service_unit', '');
			frm.set_value('modality', '');
			frm.fields_dict.appointment_details_html.html('');
		}
	},
	onload: function (frm) {
		if (frm.is_new()) {
			frm.add_fetch('radiology_examination_template', 'medical_department', 'medical_department');
			frappe.db.get_value('Healthcare Settings', '', 'default_practitioner_source', function (r) {
				if (r && r.default_practitioner_source) {
					frm.set_value('source', r.default_practitioner_source);
				}
				else {
					frm.set_value('source', '');
				}
			});
		}
	},
	inpatient_record: function (frm) {
		if (frm.doc.inpatient_record) {
			frappe.call({
				method: 'frappe.client.get',
				args: {
					doctype: 'Inpatient Record',
					name: frm.doc.inpatient_record
				},
				callback: function (r) {
					if (r.message) {
						if (r.message.source) {
							frm.set_value('source', r.message.source);
							frm.set_df_property('source', 'read_only', 1);
						}
						else {
							frm.set_value('source', '');
							frm.set_df_property('source', 'read_only', 0);
						}
						if (r.message.referring_practitioner) {
							frm.set_value('referring_practitioner', r.message.referring_practitioner);
							frm.set_df_property('referring_practitioner', 'read_only', 1);
						}
						else {
							frm.set_value('referring_practitioner', '');
							frm.set_df_property('referring_practitioner', 'read_only', 0);
						}
						if (r.message.company) {
							frm.set_value('company', r.message.company)
						}
					}
				}
			});
		}
	},
	tc_name: function(frm) {
		erpnext.utils.get_terms(frm.doc.tc_name, frm.doc, function (r) {
			if (!r.exc) {
				frm.set_value('terms', r.message);
			}
		});
	},
	source: function (frm) {
		if (frm.doc.source == 'Direct') {
			frm.set_value('referring_practitioner', '');
			frm.set_df_property('referring_practitioner', 'hidden', 1);
		}
		else if (frm.doc.source == 'External Referral' || frm.doc.source == 'Referral') {
			if (frm.doc.practitioner) {
				frm.set_df_property('referring_practitioner', 'hidden', 0);
				if (frm.doc.source == 'External Referral') {
					frappe.db.get_value('Healthcare Practitioner', frm.doc.practitioner, 'healthcare_practitioner_type', function (r) {
						if (r && r.healthcare_practitioner_type && r.healthcare_practitioner_type == 'External') {
							frm.set_value('referring_practitioner', frm.doc.practitioner);
						}
						else {
							frm.set_value('referring_practitioner', '');
						}
					});
					frm.set_df_property('referring_practitioner', 'read_only', 0);
				}
				else {
					frappe.db.get_value('Healthcare Practitioner', frm.doc.practitioner, 'healthcare_practitioner_type', function (r) {
						if (r && r.healthcare_practitioner_type && r.healthcare_practitioner_type == 'Internal') {
							frm.set_value('referring_practitioner', frm.doc.practitioner);
							frm.set_df_property('referring_practitioner', 'read_only', 1);
						}
						else {
							frm.set_value('referring_practitioner', '');
							frm.set_df_property('referring_practitioner', 'read_only', 0);
						}
					});
				}
				frm.set_df_property('referring_practitioner', 'reqd', 1);
			}
			else {
				frm.set_df_property('referring_practitioner', 'read_only', 0);
				frm.set_df_property('referring_practitioner', 'hidden', 0);
				frm.set_df_property('referring_practitioner', 'reqd', 1);
			}
		}
	},
	refresh: function (frm) {
		if(frm.doc.__islocal){
			frm.add_custom_button(__('Get from Patient Encounter'), function () {
				get_radiology_procedure_prescribed(frm);
			});
		}
		frm.set_query('patient', function () {
			return {
				filters: { 'status': 'Active' }
			};
		});
		frm.set_query('service_unit', function () {
			return {
				filters: {
					'is_group': false
				}
			};
		});
		frm.set_query('appointment', function () {
			return {
				filters: {
					'radiology_examination_template': ['not in', null],
					'status': ['in', 'Open, Scheduled']
				}
			};
		});
		frm.set_query('referring_practitioner', function () {
			if (frm.doc.source == 'External Referral') {
				return {
					filters: {
						'healthcare_practitioner_type': 'External'
					}
				};
			}
			else {
				return {
					filters: {
						'healthcare_practitioner_type': 'Internal'
					}
				};
			}
		});
	}
});

var get_radiology_procedure_prescribed = function(frm){
	if(frm.doc.patient){
		frappe.call({
			method:	'erpnext.healthcare.doctype.radiology_examination.radiology_examination.get_radiology_procedure_prescribed',
			args:	{patient: frm.doc.patient},
			callback: function(r){
				show_radiology_procedure(frm, r.message);
			}
		});
	}
	else{
		frappe.msgprint(__('Please select Patient to Radiology Procedure'));
	}
};

var show_radiology_procedure = function(frm, result){
	var d = new frappe.ui.Dialog({
		title: __('Radiology Procedure Prescriptions'),
		fields: [
			{
				fieldtype: 'HTML', fieldname: 'radiology_prescribed'
			}
		]
	});
	var html_field = d.fields_dict.radiology_prescribed.$wrapper;
	html_field.empty();
	$.each(result, function(x, y){
		var row = $(repl('<div class="col-xs-12" style="padding-top:12px; text-align:center;" >\
		<div class="col-xs-2"> %(radiology_template)s </div>\
		<div class="col-xs-2"> %(encounter)s </div>\
		<div class="col-xs-3"> %(date)s </div>\
		<div class="col-xs-1">\
		<a data-name="%(name)s" data-radiology-template="%(radiology_template)s"\
		data-encounter="%(encounter)s"\
		data-invoiced="%(invoiced)s" data-source="%(source)s" data-referring-practitioner="%(referring_practitioner)s" \
		data-insurance="%(insurance)s" data-comments="%(comments)s" href="#"><button class="btn btn-default btn-xs">Get Radiology\
		</button></a></div></div>', {name:y[0], radiology_template: y[1], encounter:y[2], invoiced:y[3],  date:y[4], source:y[5],
		referring_practitioner:y[6], insurance:y[8]? y[8]:'', comments:y[9]? y[9]:''})).appendTo(html_field);
		row.find('a').click(function() {
			frm.set_value('radiology_examination_template', $(this).attr('data-radiology-template'));
			frm.set_value('radiology_procedure_prescription', $(this).attr('data-name'));
			frm.set_df_property('patient', 'read_only', 1);
			frm.doc.invoiced = 0;
			if($(this).attr('data-invoiced') == 1){
				frm.doc.invoiced = 1;
			}
			if($(this).attr('data-comments')){
				frm.set_value('notes', $(this).attr('data-comments'));
			}
			if(frm.doc.referring_practitioner){
				frm.set_df_property('referring_practitioner', 'hidden', 0);
			}
			refresh_field('invoiced');
			refresh_field('radiology_examination_template');
			d.hide();
			return false;
		});
	});
	if(result == ''){
		var msg = 'There are no Radiology prescribed for '+frm.doc.patient;
		$(repl('<div class="col-xs-12" style="padding-top:20px;" >%(msg)s</div></div>', {msg: msg})).appendTo(html_field);
	}
	d.show();
};
