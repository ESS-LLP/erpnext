// Copyright (c) 2017, ESS LLP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Clinical Procedure', {
	setup: function(frm) {
		frm.set_query('batch_no', 'items', function(doc, cdt, cdn) {
			var item = locals[cdt][cdn];
			if(!item.item_code) {
				frappe.throw(__("Please enter Item Code to get Batch Number"));
			} else {
				if (frm.doc.status == 'In Progress') {
					var filters = {
						'item_code': item.item_code,
						'posting_date': frm.doc.start_date || frappe.datetime.nowdate()
					};
					if(frm.doc.warehouse) filters["warehouse"] = frm.doc.warehouse;
				} else {
					filters = {
						'item_code': item.item_code
					};
				}
				return {
					query : "erpnext.controllers.queries.get_batch_no",
					filters: filters
				};
			}
		});
	},
	source: function(frm){
		if(frm.doc.source=="Direct"){
			frm.set_value("referring_practitioner", "");
			frm.set_df_property("referring_practitioner", "hidden", 1);
		}else if(frm.doc.source=="Referral"){
			frm.set_value("referring_practitioner", frm.doc.practitioner);
			frm.set_df_property("referring_practitioner", "hidden", 0);
			frm.set_df_property("referring_practitioner", "read_only", 1);
			frm.set_df_property("referring_practitioner", "reqd", 1);
		}else if(frm.doc.source=="External Referral"){
			frm.set_df_property("referring_practitioner", "read_only", 0);
			frm.set_df_property("referring_practitioner", "hidden", 0);
			frm.set_df_property("referring_practitioner", "reqd", 1);
		}
	},
	refresh: function(frm) {
		frm.set_query("patient", function () {
			return {
				filters: {"disabled": 0}
			};
		});
		frm.set_query("appointment", function () {
			return {
				filters: {
					"procedure_template": ["not in", null],
					"status": ['in', 'Open, Scheduled']
				}
			};
		});
		frm.set_query("service_unit", function(){
			return {
				filters: {
					"is_group": false,
					"allow_appointments": true
				}
			};
		});
		frm.set_query("practitioner", function() {
			return {
				filters: {
					'department': frm.doc.medical_department
				}
			};
		});
		if(frm.doc.__islocal){
			frm.add_custom_button(__('Get from Patient Encounter'), function () {
				get_procedure_prescribed(frm);
			});
		}
		if(frm.doc.consume_stock){
			frm.set_indicator_formatter('item_code',
				function(doc) { return (doc.qty<=doc.actual_qty) ? "green" : "orange" ; });
		}

		if (!frm.doc.__islocal && frm.doc.status == 'In Progress'){

			if(frm.doc.consume_stock){
				var btn_label = 'Complete and Consume';
				var msg = 'Complete '+frm.doc.name+' and Consume Stock?';
			}else{
				btn_label = 'Complete';
				msg = 'Complete '+frm.doc.name+'?';
			}

			frm.add_custom_button(__(btn_label), function () {
				frappe.confirm(
					__(msg),
					function(){
						frappe.call({
							doc: frm.doc,
							method: "complete",
							callback: function(r) {
								if(!r.exc){
									cur_frm.reload_doc();
								}
							}
						});
					}
				);
			});
		}else if (!frm.doc.__islocal && frm.doc.status == 'Draft') {
			frm.add_custom_button(__("Start"), function () {
				frappe.call({
					doc: frm.doc,
					method: "start",
					callback: function(r) {
						if(!r.exc){
							if(frm.doc.status == 'Draft'){
								frappe.confirm(
									__("Stock quantity to start procedure is not available in the warehouse. Do you want to record a Stock Transfer"),
									function(){
										frappe.call({
											doc: frm.doc,
											method: "make_material_transfer",
											callback: function(r) {
												if(!r.exc){
													cur_frm.reload_doc();
													var doclist = frappe.model.sync(r.message);
													frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
												}
											}
										});
									}
								);
							}else{
								cur_frm.reload_doc();
							}
						}
					}
				});
			});
		}
		if (frm.doc.__islocal){
			frm.set_df_property("consumables", "hidden", 1);
		}else{
			frm.set_df_property("consumables", "hidden", 0);
		}
	},
	onload: function(frm){
		if(frm.doc.status == 'Completed'){
			frm.set_df_property("items", "read_only", 1);
		}
		if(frm.is_new()) {
			frm.add_fetch("procedure_template", "medical_department", "medical_department");
			frm.set_value("start_time", null);
		}
	},
	patient: function(frm) {
		if(frm.doc.patient){
			frappe.call({
				"method": "erpnext.healthcare.doctype.patient.patient.get_patient_detail",
				args: {
					patient: frm.doc.patient
				},
				callback: function (data) {
					let age = "";
					if(data.message.dob){
						age = calculate_age(data.message.dob);
					}else if (data.message.age){
						age = data.message.age;
						if(data.message.age_as_on){
							age = age+" as on "+data.message.age_as_on;
						}
					}
					frm.set_value("patient_age", age);
					frm.set_value("patient_sex", data.message.sex);
				}
			});
		}else{
			frm.set_value("patient_age", "");
			frm.set_value("patient_sex", "");
		}
	},
	appointment: function(frm) {
		if(frm.doc.appointment){
			frappe.call({
				"method": "frappe.client.get",
				args: {
					doctype: "Patient Appointment",
					name: frm.doc.appointment
				},
				callback: function (data) {
					frm.set_value("patient", data.message.patient);
					frm.set_value("procedure_template", data.message.procedure_template);
					frm.set_value("medical_department", data.message.department);
					frm.set_value("start_date", data.message.appointment_date);
					frm.set_value("start_time", data.message.appointment_time);
					frm.set_value("notes", data.message.notes);
					frm.set_value("service_unit", data.message.service_unit);
					frm.set_value( "source", data.message.source);
					if(data.message.referring_practitioner){
						frm.set_value( "referring_practitioner", data.message.referring_practitioner);
					}
				}
			});
		}
	},
	procedure_template: function(frm) {
		if(frm.doc.procedure_template){
			frappe.call({
				"method": "frappe.client.get",
				args: {
					doctype: "Clinical Procedure Template",
					name: frm.doc.procedure_template
				},
				callback: function (data) {
					frm.set_value("medical_department", data.message.medical_department);
					frm.set_value("consume_stock", data.message.consume_stock);
					if(!frm.doc.warehouse){
						frappe.call({
							method: "frappe.client.get_value",
							args: {
								doctype: "Stock Settings",
								fieldname: "default_warehouse"
							},
							callback: function (data) {
								frm.set_value("warehouse", data.message.default_warehouse);
							}
						});
					}
				}
			});
		}else{
			frm.set_value("consume_stock", 0);
		}
	},
	service_unit: function(frm) {
		if(frm.doc.service_unit){
			frappe.call({
				method: "frappe.client.get_value",
				args:{
					fieldname: "warehouse",
					doctype: "Healthcare Service Unit",
					filters:{name: frm.doc.service_unit},
				},
				callback: function(data) {
					if(data.message){
						frm.set_value("warehouse", data.message.warehouse);
					}
				}
			});
		}
	},
	practitioner: function(frm) {
		if(frm.doc.practitioner){
			frappe.call({
				"method": "frappe.client.get",
				args: {
					doctype: "Healthcare Practitioner",
					name: frm.doc.practitioner
				},
				callback: function (data) {
					frappe.model.set_value(frm.doctype,frm.docname, "medical_department",data.message.department);
				}
			});
		}
	}
});

var get_procedure_prescribed = function(frm){
	if(frm.doc.patient){
		frappe.call({
			method:"erpnext.healthcare.doctype.patient_appointment.patient_appointment.get_procedure_prescribed",
			args: {patient: frm.doc.patient},
			callback: function(r){
				show_procedure_templates(frm, r.message);
			}
		});
	}
	else{
		frappe.msgprint("Please select Patient to get prescribed procedure");
	}
};

var show_procedure_templates = function(frm, result){
	var d = new frappe.ui.Dialog({
		title: __("Prescribed Procedures"),
		fields: [
			{
				fieldtype: "HTML", fieldname: "procedure_template"
			}
		]
	});
	var html_field = d.fields_dict.procedure_template.$wrapper;
	html_field.empty();
	$.each(result, function(x, y){
		var row = $(repl('<div class="col-xs-12" style="padding-top:12px; text-align:center;" >\
		<div class="col-xs-5"> %(encounter)s <br> %(consulting_practitioner)s <br> %(encounter_date)s </div>\
		<div class="col-xs-5"> %(procedure_template)s <br>%(practitioner)s  <br> %(date)s</div>\
		<div class="col-xs-2">\
		<a data-name="%(name)s" data-procedure-template="%(procedure_template)s"\
		data-encounter="%(encounter)s" data-practitioner="%(practitioner)s"\
		data-date="%(date)s"  data-department="%(department)s" data-source="%(source)s" data-referring-practitioner="%(referring_practitioner)s">\
		<button class="btn btn-default btn-xs">Add\
		</button></a></div></div><div class="col-xs-12"><hr/><div/>', {name:y[0], procedure_template: y[1],
				encounter:y[2], consulting_practitioner:y[3], encounter_date:y[4],
				practitioner:y[5]? y[5]:'', date: y[6]? y[6]:'', department: y[7]? y[7]:'', source:y[8], referring_practitioner:y[9]})).appendTo(html_field);
		row.find("a").click(function() {
			frm.doc.procedure_template = $(this).attr("data-procedure-template");
			frm.doc.prescription = $(this).attr("data-name");
			frm.doc.practitioner = $(this).attr("data-practitioner");
			frm.doc.start_date = $(this).attr("data-date");
			frm.doc.medical_department = $(this).attr("data-department");
			frm.doc.source =  $(this).attr("data-source");
			frm.doc.referring_practitioner= $(this).attr("data-referring-practitioner")
			if(frm.doc.referring_practitioner){
				frm.set_df_property("referring_practitioner", "hidden", 0);
			}
			refresh_field("procedure_template");
			refresh_field("prescription");
			refresh_field("start_date");
			refresh_field("practitioner");
			refresh_field("medical_department");
			refresh_field("source");
			refresh_field("referring_practitioner");
			d.hide();
			return false;
		});
	});
	if(!result || result.length < 1){
		var msg = "There are no procedure prescribed for patient "+frm.doc.patient;
		$(repl('<div class="text-left">%(msg)s</div>', {msg: msg})).appendTo(html_field);
	}
	d.show();
};

cur_frm.set_query("procedure_template", function(doc) {
	return {
		filters: {
			'medical_department': doc.medical_department
		}
	};
});

cur_frm.set_query("appointment", function() {
	return {
		filters: {
			status:['in',["Open"]]
		}
	};
});

frappe.ui.form.on('Clinical Procedure Item', {
	qty: function(frm, cdt, cdn){
		var d = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "transfer_qty", d.qty*d.conversion_factor);
	},
	uom: function(doc, cdt, cdn){
		var d = locals[cdt][cdn];
		if(d.uom && d.item_code){
			return frappe.call({
				method: "erpnext.stock.doctype.stock_entry.stock_entry.get_uom_details",
				args: {
					item_code: d.item_code,
					uom: d.uom,
					qty: d.qty
				},
				callback: function(r) {
					if(r.message) {
						frappe.model.set_value(cdt, cdn, r.message);
					}
				}
			});
		}
	},
	item_code: function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		let args = null;
		if(d.item_code) {
			args = {
				'doctype' : "Clinical Procedure",
				'item_code' : d.item_code,
				'company' : frm.doc.company,
				'warehouse': frm.doc.warehouse
			};
			return frappe.call({
				method: "erpnext.stock.get_item_details.get_item_details",
				args: {args: args},
				callback: function(r) {
					if(r.message) {
						frappe.model.set_value(cdt, cdn, "item_name", r.message.item_name);
						frappe.model.set_value(cdt, cdn, "stock_uom", r.message.stock_uom);
						frappe.model.set_value(cdt, cdn, "conversion_factor", r.message.conversion_factor);
						frappe.model.set_value(cdt, cdn, "actual_qty", r.message.actual_qty);
						refresh_field("items");
					}
				}
			});
		}
	}
});

var calculate_age = function(birth) {
	var ageMS = Date.parse(Date()) - Date.parse(birth);
	var age = new Date();
	age.setTime(ageMS);
	var years =  age.getFullYear() - 1970;
	return  years + " Year(s) " + age.getMonth() + " Month(s) " + age.getDate() + " Day(s)";
};

// List Stock items
cur_frm.set_query("item_code", "items", function() {
	return {
		filters: {
			is_stock_item:1
		}
	};
});
