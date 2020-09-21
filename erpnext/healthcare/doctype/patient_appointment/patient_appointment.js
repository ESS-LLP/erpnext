// Copyright (c) 2016, ESS LLP and contributors
// For license information, please see license.txt
frappe.provide('erpnext.queries');
frappe.ui.form.on('Patient Appointment', {
	setup: function (frm) {
		frm.custom_make_buttons = {
			'Vital Signs': 'Vital Signs',
			'Patient Encounter': 'Patient Encounter'
		};
	},

	onload: function (frm) {
		if (frm.is_new()) {
			frm.set_value('appointment_time', null);
			frm.disable_save();
		}
		if(frm.doc.source){
			set_source_referring_practitioner(frm)
		}
	},

	refresh: function (frm) {
		frm.set_query('patient', function () {
			return {
				filters: { 'status': 'Active' }
			};
		});
		frm.set_query('practitioner', function () {
			return {
				filters: {
					'department': frm.doc.department
				}
			};
		});
		frm.set_query('service_unit', function () {
			return {
				filters: {
					'is_group': false,
					'allow_appointments': true,
					'company': frm.doc.company,
				}
			};
		});
		frm.set_query('radiology_examination_template', function () {
			return {
				filters: {
					'modality_type': frm.doc.modality_type || ''
				}
			};
		});

		frm.set_query('referring_practitioner', function() {
			if(frm.doc.source == 'External Referral'){
				return {
					filters: {
						'healthcare_practitioner_type': 'External'
					}
				};
			}
			else{
				return {
					filters: {
						'healthcare_practitioner_type': 'Internal'
					}
				};
			}
		});

		if (frm.is_new()) {
			frm.page.set_primary_action(__('Check Availability'), function () {
				if (!frm.doc.patient) {
					frappe.msgprint({
						title: __('Not Allowed'),
						message: __('Please select Patient first'),
						indicator: 'red'
					});
				} else {
					frappe.call({
						method: 'erpnext.healthcare.doctype.patient_appointment.patient_appointment.check_payment_fields_reqd',
						args: { 'patient': frm.doc.patient },
						callback: function (data) {
							if (data.message == true) {
								if (frm.doc.mode_of_payment && frm.doc.paid_amount) {
									check_and_set_availability(frm);
								}
								if (!frm.doc.mode_of_payment) {
									frappe.msgprint({
										title: __('Not Allowed'),
										message: __('Please select a Mode of Payment first'),
										indicator: 'red'
									});
								}
								if (!frm.doc.paid_amount) {
									frappe.msgprint({
										title: __('Not Allowed'),
										message: __('Please set the Paid Amount first'),
										indicator: 'red'
									});
								}
							} else {
								check_and_set_availability(frm);
							}
						}
					});
				}
			});
		} else {
			frm.page.set_primary_action(__('Save'), () => frm.save());
		}

		if (frm.doc.patient) {
			frm.add_custom_button(__('Patient History'), function () {
				frappe.route_options = { 'patient': frm.doc.patient };
				frappe.set_route('patient_history');
			}, __('View'));
		}

		if (frm.doc.status == 'Open' || (frm.doc.status == 'Scheduled' && !frm.doc.__islocal)) {
			frm.add_custom_button(__('Cancel'), function () {
				update_status(frm, 'Cancelled');
			});
			frm.add_custom_button(__('Reschedule'), function () {
				check_and_set_availability(frm);
			});

			if (frm.doc.procedure_template) {
				frm.add_custom_button(__('Clinical Procedure'), function () {
					frappe.model.open_mapped_doc({
						method: 'erpnext.healthcare.doctype.clinical_procedure.clinical_procedure.make_procedure',
						frm: frm,
					});
				}, __('Create'));
			} else if (frm.doc.therapy_type) {
				frm.add_custom_button(__('Therapy Session'), function () {
					frappe.model.open_mapped_doc({
						method: 'erpnext.healthcare.doctype.therapy_session.therapy_session.create_therapy_session',
						frm: frm,
					})
				}, 'Create');
			} else if (frm.doc.radiology_examination_template) {
				frm.add_custom_button(__('Radiology Examination'), function () {
					create_radiology_exam(frm);
				}, 'Create');
			} else {
				frm.add_custom_button(__('Patient Encounter'), function () {
					frappe.model.open_mapped_doc({
						method: 'erpnext.healthcare.doctype.patient_appointment.patient_appointment.make_encounter',
						frm: frm,
					});
				}, __('Create'));
			}

			frm.add_custom_button(__('Vital Signs'), function () {
				create_vital_signs(frm);
			}, __('Create'));
		}
	},

	patient: function (frm) {
		if (frm.doc.patient) {
			frm.trigger('toggle_payment_fields');
		} else {
			frm.set_value('patient_name', '');
			frm.set_value('patient_sex', '');
			frm.set_value('patient_age', '');
			frm.set_value('inpatient_record', '');
		}
	},

	therapy_type: function (frm) {
		if (frm.doc.therapy_type) {
			frappe.db.get_value('Therapy Type', frm.doc.therapy_type, 'default_duration', (r) => {
				if (r.default_duration) {
					frm.set_value('duration', r.default_duration)
				}
			});
		}
	},

	service_unit: function (frm) {
		if (!frm.doc.service_unit) {
			frm.set_value('modality_type', '');
		}
	},

	get_procedure_from_encounter: function (frm) {
		get_prescribed_procedure(frm);
	},

	get_ordered_radiology_procedures: function (frm) {
		get_radiology_prescribed(frm);
	},

	radiology_examination_template: function (frm) {
		if (frm.doc.radiology_examination_template) {
			frm.set_df_property('service_unit', 'reqd', true);
		}
		else {
			frm.set_df_property('service_unit', 'reqd', false);
		}
	},

	toggle_payment_fields: function (frm) {
		frappe.call({
			method: 'erpnext.healthcare.doctype.patient_appointment.patient_appointment.check_payment_fields_reqd',
			args: { 'patient': frm.doc.patient },
			callback: function (data) {
				if (data.message.fee_validity) {
					// if fee validity exists and automated appointment invoicing is enabled,
					// show payment fields as non-mandatory
					frm.toggle_display('mode_of_payment', 0);
					frm.toggle_display('paid_amount', 0);
					frm.toggle_reqd('mode_of_payment', 0);
					frm.toggle_reqd('paid_amount', 0);
				} else {
					// if automated appointment invoicing is disabled, hide fields
					frm.toggle_display('mode_of_payment', data.message ? 1 : 0);
					frm.toggle_display('paid_amount', data.message ? 1 : 0);
					frm.toggle_reqd('mode_of_payment', data.message ? 1 : 0);
					frm.toggle_reqd('paid_amount', data.message ? 1 : 0);
				}
			}
		});
	},

	get_prescribed_therapies: function (frm) {
		if (frm.doc.patient) {
			frappe.call({
				method: "erpnext.healthcare.doctype.patient_appointment.patient_appointment.get_prescribed_therapies",
				args: { patient: frm.doc.patient },
				callback: function (r) {
					if (r.message) {
						show_therapy_types(frm, r.message);
					} else {
						frappe.msgprint({
							title: __('Not Therapies Prescribed'),
							message: __('There are no Therapies prescribed for Patient {0}', [frm.doc.patient.bold()]),
							indicator: 'blue'
						});
					}
				}
			});
		}
	},

	source: function(frm){
		if(frm.doc.source){
			set_source_referring_practitioner(frm);
		}
	}
});

let check_and_set_availability = function (frm) {
	let selected_slot = null;
	let service_unit = null;
	let duration = null;

	show_availability();

	function show_empty_state(practitioner, appointment_date) {
		frappe.msgprint({
			title: __('Not Available'),
			message: __('Healthcare Practitioner {0} not available on {1}', [practitioner.bold(), appointment_date.bold()]),
			indicator: 'red'
		});
	}

	function show_availability() {
		let selected_practitioner = '';
		let d = new frappe.ui.Dialog({
			title: __('Available slots'),
			fields: [
				{ fieldtype: 'Link', options: 'Medical Department', reqd: 1, fieldname: 'department', label: 'Medical Department' },
				{ fieldtype: 'Column Break' },
				{ fieldtype: 'Link', options: 'Healthcare Practitioner', reqd: 1, fieldname: 'practitioner', label: 'Healthcare Practitioner' },
				{ fieldtype: 'Column Break' },
				{ fieldtype: 'Date', reqd: 1, fieldname: 'appointment_date', label: 'Date' },
				{ fieldtype: 'Section Break' },
				{ fieldtype: 'HTML', fieldname: 'available_slots' }

			],
			primary_action_label: __('Book'),
			primary_action: function () {
				frm.set_value('appointment_time', selected_slot);
				if (!frm.doc.duration) {
					frm.set_value('duration', duration);
				}
				frm.set_value('practitioner', d.get_value('practitioner'));
				frm.set_value('department', d.get_value('department'));
				frm.set_value('appointment_date', d.get_value('appointment_date'));
				if (service_unit) {
					frm.set_value('service_unit', service_unit);
				}
				d.hide();
				frm.enable_save();
				frm.save();
				d.get_primary_btn().attr('disabled', true);
			}
		});

		d.set_values({
			'department': frm.doc.department,
			'practitioner': frm.doc.practitioner,
			'appointment_date': frm.doc.appointment_date
		});

		d.fields_dict['department'].df.onchange = () => {
			d.set_values({
				'practitioner': ''
			});
			let department = d.get_value('department');
			if (department) {
				d.fields_dict.practitioner.get_query = function () {
					return {
						filters: {
							'department': department
						}
					};
				};
			}
		};

		// disable dialog action initially
		d.get_primary_btn().attr('disabled', true);

		// Field Change Handler

		let fd = d.fields_dict;

		d.fields_dict['appointment_date'].df.onchange = () => {
			show_slots(d, fd);
		};
		d.fields_dict['practitioner'].df.onchange = () => {
			if (d.get_value('practitioner') && d.get_value('practitioner') != selected_practitioner) {
				selected_practitioner = d.get_value('practitioner');
				show_slots(d, fd);
			}
		};
		d.show();
	}

	function show_slots(d, fd) {
		if (d.get_value('appointment_date') && d.get_value('practitioner')) {
			fd.available_slots.html('');
			frappe.call({
				method: 'erpnext.healthcare.doctype.patient_appointment.patient_appointment.get_availability_data',
				args: {
					practitioner: d.get_value('practitioner'),
					date: d.get_value('appointment_date')
				},
				callback: (r) => {
					let data = r.message;
					if (data.slot_details.length > 0) {
						let $wrapper = d.fields_dict.available_slots.$wrapper;

						// make buttons for each slot
						let slot_details = data.slot_details;
						let slot_html = '';
						for (let i = 0; i < slot_details.length; i++) {
							slot_html = slot_html + `<label>${slot_details[i].slot_name}</label>`;
							slot_html = slot_html + `<br/>` + slot_details[i].avail_slot.map(slot => {
								let appointment_count = 0;
								let disabled = false;
								let start_str = slot.from_time;
								let slot_start_time = moment(slot.from_time, 'HH:mm:ss');
								let slot_to_time = moment(slot.to_time, 'HH:mm:ss');
								let interval = (slot_to_time - slot_start_time) / 60000 | 0;
								// iterate in all booked appointments, update the start time and duration
								slot_details[i].appointments.forEach(function (booked) {
									let booked_moment = moment(booked.appointment_time, 'HH:mm:ss');
									let end_time = booked_moment.clone().add(booked.duration, 'minutes');
									// Deal with 0 duration appointments
									if (booked_moment.isSame(slot_start_time) || booked_moment.isBetween(slot_start_time, slot_to_time)) {
										if(booked.duration == 0){
											disabled = true;
											return false;
										}
									}
									// Check for overlaps considering appointment duration
									if(slot_details[i].allow_overlap != 1){
										if (slot_start_time.isBefore(end_time) && slot_to_time.isAfter(booked_moment)) {
											// There is an overlap
											disabled = true;
											return false;
										}
									}
									else{
										if(slot_start_time.isBefore(end_time) && slot_to_time.isAfter(booked_moment)){
											appointment_count++
										}
										if(appointment_count>=slot_details[i].service_unit_capacity){
											// There is an overlap
											disabled = true;
											return false;
										}
									}
								});
								let count=''
								if(slot_details[i].allow_overlap==1 && slot_details[i].service_unit_capacity>1){
									count=" - "+(slot_details[i].service_unit_capacity - appointment_count)
									// document.getElementById("count").style.fontSize = "xx-large";
								}
								return `<button class="btn btn-default"
									data-name=${start_str}
									data-duration=${interval}
									data-service-unit="${slot_details[i].service_unit || ''}"
									style="margin: 0 10px 10px 0; width: 72px;" ${ disabled ? 'disabled="disabled"' : "" }>
									${start_str.substring(0, start_str.length - 3)} ${count}
								</button>`;
							}).join("");
							slot_html = slot_html + `<br/>`;
						}

						$wrapper
							.css('margin-bottom', 0)
							.addClass('text-center')
							.html(slot_html);

						// primtary button when clicked
						$wrapper.on('click', 'button', function() {
							let $btn = $(this);
							$wrapper.find('button').removeClass('btn-primary');
							$btn.addClass('btn-primary');
							selected_slot = $btn.attr('data-name');
							service_unit = $btn.attr('data-service-unit');
							duration = $btn.attr('data-duration');
							// enable dialog action
							d.get_primary_btn().attr('disabled', null);
						});

					} else {
						//	fd.available_slots.html('Please select a valid date.'.bold())
						show_empty_state(d.get_value('practitioner'), d.get_value('appointment_date'));
					}
				},
				freeze: true,
				freeze_message: __('Fetching records......')
			});
		} else {
			fd.available_slots.html(__('Appointment date and Healthcare Practitioner are Mandatory').bold());
		}
	}
};

let get_prescribed_procedure = function (frm) {
	if (frm.doc.patient) {
		frappe.call({
			method: 'erpnext.healthcare.doctype.patient_appointment.patient_appointment.get_procedure_prescribed',
			args: { patient: frm.doc.patient },
			callback: function (r) {
				if (r.message && r.message.length) {
					show_procedure_templates(frm, r.message);
				} else {
					frappe.msgprint({
						title: __('Not Found'),
						message: __('No Prescribed Procedures found for the selected Patient')
					});
				}
			}
		});
	} else {
		frappe.msgprint({
			title: __('Not Allowed'),
			message: __('Please select a Patient first')
		});
	}
};

let show_procedure_templates = function (frm, result) {
	let d = new frappe.ui.Dialog({
		title: __('Prescribed Procedures'),
		fields: [
			{
				fieldtype: 'HTML', fieldname: 'procedure_template'
			}
		]
	});
	let html_field = d.fields_dict.procedure_template.$wrapper;
	html_field.empty();
	$.each(result, function (x, y) {
		let row = $(repl('<div class="col-xs-12" style="padding-top:12px; text-align:center;" >\
		<div class="col-xs-5"> %(encounter)s <br> %(consulting_practitioner)s <br> %(encounter_date)s </div>\
		<div class="col-xs-5"> %(procedure_template)s <br>%(practitioner)s  <br> %(date)s</div>\
		<div class="col-xs-2">\
		<a data-name="%(name)s" data-procedure-template="%(procedure_template)s"\
		data-encounter="%(encounter)s" data-practitioner="%(practitioner)s"\
		data-date="%(date)s" data-department="%(department)s" data-source="%(source)s"\
		data-referring-practitioner="%(referring_practitioner)s"> <button class="btn btn-default btn-xs">Add\
		</button></a></div></div><div class="col-xs-12"><hr/><div/>', {name:y[0], procedure_template: y[1],
				encounter:y[2], consulting_practitioner:y[3], encounter_date:y[4],
				practitioner:y[5]? y[5]:'', date: y[6]? y[6]:'', department: y[7]? y[7]:'',  source: y[8]? y[8]:'',
				referring_practitioner: y[9]? y[9]:''})).appendTo(html_field);
		row.find("a").click(function() {
			frm.doc.procedure_template = $(this).attr('data-procedure-template');
			frm.doc.procedure_prescription = $(this).attr('data-name');
			frm.doc.practitioner = $(this).attr('data-practitioner');
			frm.doc.appointment_date = $(this).attr('data-date');
			frm.doc.department = $(this).attr('data-department');
			frm.doc.source = $(this).attr('data-source');
			frm.set_df_property('source', 'read_only', 1);
			frm.doc.referring_practitioner = $(this).attr('data-referring-practitioner');
			if(frm.doc.referring_practitioner){
				frm.set_df_property('referring_practitioner', 'hidden', 0);
				frm.set_df_property('referring_practitioner', 'read_only', 1);
			}
			frm.refresh_field('procedure_template');
			frm.refresh_field('procedure_prescription');
			frm.refresh_field('appointment_date');
			frm.refresh_field('practitioner');
			frm.refresh_field('department');
			frm.refresh_field('source');
			frm.refresh_field('referring_practitioner');
			d.hide();
			return false;
		});
	});
	if (!result) {
		let msg = __('There are no procedure prescribed for ') + frm.doc.patient;
		$(repl('<div class="col-xs-12" style="padding-top:20px;" >%(msg)s</div></div>', { msg: msg })).appendTo(html_field);
	}
	d.show();
};

let show_therapy_types = function (frm, result) {
	var d = new frappe.ui.Dialog({
		title: __('Prescribed Therapies'),
		fields: [
			{
				fieldtype: 'HTML', fieldname: 'therapy_type'
			}
		]
	});
	var html_field = d.fields_dict.therapy_type.$wrapper;
	$.each(result, function (x, y) {
		var row = $(repl('<div class="col-xs-12" style="padding-top:12px; text-align:center;" >\
		<div class="col-xs-5"> %(encounter)s <br> %(practitioner)s <br> %(date)s </div>\
		<div class="col-xs-5"> %(therapy)s </div>\
		<div class="col-xs-2">\
		<a data-therapy="%(therapy)s" data-therapy-plan="%(therapy_plan)s" data-name="%(name)s"\
		data-encounter="%(encounter)s" data-practitioner="%(practitioner)s"\
		data-date="%(date)s"  data-department="%(department)s" data-source="%(source)s"\
		data-referring-practitioner="%(referring_practitioner)s"> <button class="btn btn-default btn-xs">Add\
		</button></a></div></div><div class="col-xs-12"><hr/><div/>', {therapy:y[0],
		name: y[1], encounter:y[2], practitioner:y[3], date:y[4],
		department:y[6]? y[6]:'', therapy_plan:y[5],   source: y[7]? y[7]:'', referring_practitioner: y[8]? y[8]:''})).appendTo(html_field);

		row.find("a").click(function () {
			frm.doc.therapy_type = $(this).attr("data-therapy");
			frm.doc.practitioner = $(this).attr("data-practitioner");
			frm.doc.department = $(this).attr("data-department");
			frm.doc.therapy_plan = $(this).attr("data-therapy-plan");
			frm.doc.source = $(this).attr('data-source');
			frm.set_df_property('source', 'read_only', 1);
			frm.doc.referring_practitioner = $(this).attr('data-referring-practitioner');
			if(frm.doc.referring_practitioner){
				frm.set_df_property('referring_practitioner', 'hidden', 0);
				frm.set_df_property('referring_practitioner', 'read_only', 1);
			}
			frm.refresh_field("therapy_type");
			frm.refresh_field("practitioner");
			frm.refresh_field("department");
			frm.refresh_field("therapy-plan");
			frm.refresh_field('source');
			frm.refresh_field('referring_practitioner');
			frappe.db.get_value('Therapy Type', frm.doc.therapy_type, 'default_duration', (r) => {
				if (r.default_duration) {
					frm.set_value('duration', r.default_duration)
				}
			});
			d.hide();
			return false;
		});
	});
	d.show();
};

let create_vital_signs = function (frm) {
	if (!frm.doc.patient) {
		frappe.throw(__('Please select patient'));
	}
	frappe.route_options = {
		'patient': frm.doc.patient,
		'appointment': frm.doc.name,
		'company': frm.doc.company
	};
	frappe.new_doc('Vital Signs');
};

let create_radiology_exam = function (frm) {
	var doc = frm.doc;
	frappe.call({
		method: "erpnext.healthcare.doctype.radiology_examination.radiology_examination.create_radiology_examination",
		args: { appointment: doc.name },
		callback: function (data) {
			if (!data.exc) {
				var doclist = frappe.model.sync(data.message);
				frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
			}
		}
	});
};

let update_status = function (frm, status) {
	let doc = frm.doc;
	frappe.confirm(__('Are you sure you want to cancel this appointment?'),
		function () {
			frappe.call({
				method: 'erpnext.healthcare.doctype.patient_appointment.patient_appointment.update_status',
				args: { appointment_id: doc.name, status: status },
				callback: function (data) {
					if (!data.exc) {
						frm.reload_doc();
					}
				}
			});
		}
	);
};

frappe.ui.form.on('Patient Appointment', 'practitioner', function (frm) {
	if (frm.doc.practitioner) {
		frappe.call({
			method: 'frappe.client.get',
			args: {
				doctype: 'Healthcare Practitioner',
				name: frm.doc.practitioner
			},
			callback: function (data) {
				frappe.model.set_value(frm.doctype, frm.docname, 'department', data.message.department);
				frappe.model.set_value(frm.doctype, frm.docname, 'paid_amount', data.message.op_consulting_charge);
				frappe.model.set_value(frm.doctype, frm.docname, 'billing_item', data.message.op_consulting_charge_item);
			}
		});
	}
});

frappe.ui.form.on('Patient Appointment', 'patient', function (frm) {
	if (frm.doc.patient) {
		frappe.call({
			method: 'frappe.client.get',
			args: {
				doctype: 'Patient',
				name: frm.doc.patient
			},
			callback: function (data) {
				let age = null;
				if (data.message.dob) {
					age = calculate_age(data.message.dob);
				}
				frappe.model.set_value(frm.doctype, frm.docname, 'patient_age', age);
			}
		});
	}
});

frappe.ui.form.on('Patient Appointment', 'appointment_type', function (frm) {
	if (frm.doc.appointment_type) {
		frappe.call({
			method: 'frappe.client.get',
			args: {
				doctype: 'Appointment Type',
				name: frm.doc.appointment_type
			},
			callback: function (data) {
				frappe.model.set_value(frm.doctype, frm.docname, 'duration', data.message.default_duration);
			}
		});
	}
});

let calculate_age = function (birth) {
	let ageMS = Date.parse(Date()) - Date.parse(birth);
	let age = new Date();
	age.setTime(ageMS);
	let years = age.getFullYear() - 1970;
	return years + ' Year(s) ' + age.getMonth() + ' Month(s) ' + age.getDate() + ' Day(s)';
};

let get_radiology_prescribed = function (frm) {
	if (frm.doc.patient) {
		frappe.call({
			method: 'erpnext.healthcare.doctype.radiology_examination.radiology_examination.get_radiology_procedure_prescribed',
			args: { patient: frm.doc.patient },
			callback: function (r) {
				show_radiology_procedure(frm, r.message);
			}
		});
	}
	else {
		frappe.msgprint('Please select Patient to get prescribed procedure');
	}
};

let show_radiology_procedure = function (frm, result) {
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
	$.each(result, function (x, y) {
		var row = $(repl('<div class="col-xs-12" style="padding-top:12px; text-align:center;" >\
		<div class="col-xs-2"> %(radiology_procedure)s </div>\
		<div class="col-xs-2"> %(encounter)s </div>\
		<div class="col-xs-3"> %(date)s </div>\
		<div class="col-xs-1">\
		<a data-name="%(name)s" data-radiology-procedure="%(radiology_procedure)s"\
		data-encounter="%(encounter)s"\
		data-invoiced="%(invoiced)s" data-source="%(source)s"\
		data-referring-practitioner="%(referring_practitioner)s" data-comments="%(comments)s" href="#">\
		<button class="btn btn-default btn-xs">Get Radiology\
		</button></a></div></div>', { name: y[0], radiology_procedure: y[1], encounter: y[2], invoiced: y[3], date: y[4],
			source:y[5], referring_practitioner:y[6],comments: y[9]})).appendTo(html_field);
		row.find('a').click(function () {
			frm.set_value('radiology_examination_template', $(this).attr('data-radiology-procedure'));
			frm.set_value('radiology_procedure_prescription', $(this).attr('data-name'));
			// frm.set_df_property('radiology_procedure', 'read_only', 1);
			frm.set_df_property('patient', 'read_only', 1);
			frm.doc.invoiced = 0;
			if ($(this).attr('data-invoiced') == 1) {
				frm.doc.invoiced = 1;
			}
			if ($(this).attr('data-comments')) {
				frm.set_value('notes', $(this).attr('data-comments'));
			}
			frm.set_value('source', $(this).attr('data-source'));
			frm.set_value('referring_practitioner', $(this).attr('data-referring-practitioner'));
			frappe.db.get_value('Radiology Examination Template', frm.doc.radiology_examination_template, 'modality_type', function (r) {
				if (r && r.modality_type) {
					frm.set_value('modality_type', r.modality_type);
				}
				else {
					frm.set_value('modality_type', '');
				}
			});
			refresh_field('radiology_procedure_prescription');
			refresh_field('invoiced');
			refresh_field('radiology_examination_template');
			d.hide();
			return false;
		});
	});
	if (result == '') {
		var msg = 'There are no Radiology prescribed for ' + frm.doc.patient;
		$(repl('<div class="col-xs-12" style="padding-top:20px;" >%(msg)s</div></div>', { msg: msg })).appendTo(html_field);
	}
	d.show();
};

let set_source_referring_practitioner = function (frm) {
	if(frm.doc.source == 'Direct'){
		frm.set_value('referring_practitioner', '');
		frm.set_df_property('referring_practitioner', 'hidden', 1);
		frm.set_df_property('referring_practitioner', 'reqd', 0);
	}
	else if(frm.doc.source == 'External Referral' || frm.doc.source == 'Referral') {
		if(frm.doc.practitioner){
			frm.set_df_property('referring_practitioner', 'hidden', 0);
			if(frm.doc.source == 'External Referral'){
				frappe.db.get_value('Healthcare Practitioner', frm.doc.practitioner, 'healthcare_practitioner_type', function(r) {
					if(r && r.healthcare_practitioner_type && r.healthcare_practitioner_type == 'External'){
						frm.set_value('referring_practitioner', frm.doc.practitioner);
					}
					else{
						frm.set_value('referring_practitioner', '');
					}
				});
				frm.set_df_property('referring_practitioner', 'read_only', 0);
			}
			else{
				frappe.db.get_value('Healthcare Practitioner', frm.doc.practitioner, 'healthcare_practitioner_type', function(r) {
					if(r && r.healthcare_practitioner_type && r.healthcare_practitioner_type == 'Internal'){
						frm.set_value('referring_practitioner', frm.doc.practitioner);
						frm.set_df_property('referring_practitioner', 'read_only', 1);
					}
					else{
						frm.set_value('referring_practitioner', '');
						frm.set_df_property('referring_practitioner', 'read_only', 0);
					}
				});
			}
			frm.set_df_property('referring_practitioner', 'reqd', 1);
		}
		else{
			frm.set_df_property('referring_practitioner', 'read_only', 0);
			frm.set_df_property('referring_practitioner', 'hidden', 0);
			frm.set_df_property('referring_practitioner', 'reqd', 1);
		}
	}
};
