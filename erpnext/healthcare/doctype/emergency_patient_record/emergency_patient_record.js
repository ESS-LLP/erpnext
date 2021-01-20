// Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Emergency Patient Record', {

	// setup: function(frm) {
	// 	frm.set_indicator_formatter('patient',
	// 	function(frm) {
	// 		return (frm.doc.active == 1 ? 'green' : 'light-blue');
	// 	});
	// },
	refresh: function(frm) {
		if (!frm.doc.__islocal) {
			if (frm.doc.status == 'Active') {
				frm.add_custom_button(__('Mark As Left'), function () {
					frm.set_value('status', 'Left');
				frm.save();
				});
			}
			if (frm.doc.status != 'Left') {
				frm.add_custom_button(__('Record Consumption'), function() {
				create_delivery_note(frm);
				});

				if (!frm.doc.inpatient_record_created) {
					frm.add_custom_button(__('Schedule Admission'), function() {
						schedule_inpatient(frm);
					})
				}

				frm.add_custom_button(__('Patient Encounter'), function () {
				create_encounter(frm);
				}, __('Create'));


				frm.add_custom_button(__('Vital Signs'), function () {
				create_vital_signs(frm);
				}, __('Create'));

				// if(frm.doc.invoiced != 1){
				frm.add_custom_button(__('Sales Invoice'), function(){
				create_invoice(frm);
				}, __('Create'));
				// }

				if (!frm.doc.medico_legal_record_created) {
					frm.add_custom_button(__('Medico Legal Record'), function () {
						create_medico_legal_record(frm);
					}, __('Create'));
				}

				if (frm.doc.status != 'Active') {
					frm.add_custom_button(__('IP Record'), function(){
						frappe.route_options = {'admission_encounter': frm.doc.name};
						frappe.set_route('List', 'Inpatient Record');
				});
				}
			}
		}
	}
});

var schedule_inpatient = function(frm) {
	var dialog = new frappe.ui.Dialog({
		title: 'Patient Admission',
		fields: [
			{fieldtype: 'Link', label: 'Medical Department', fieldname: 'medical_department', options: 'Medical Department', reqd: 1},
			{fieldtype: 'Link', label: 'Healthcare Practitioner (Primary)', fieldname: 'primary_practitioner', options: 'Healthcare Practitioner', reqd: 1},
			{fieldtype: 'Link', label: 'Healthcare Practitioner (Secondary)', fieldname: 'secondary_practitioner', options: 'Healthcare Practitioner'},
			{fieldtype: 'Column Break'},
			{fieldtype: 'Date', label: 'Admission Ordered For', fieldname: 'admission_ordered_for', default: 'Today'},
			{fieldtype: 'Link', label: 'Service Unit Type', fieldname: 'service_unit_type', options: 'Healthcare Service Unit Type'},
			{fieldtype: 'Int', label: 'Expected Length of Stay', fieldname: 'expected_length_of_stay'},
			{fieldtype: 'Section Break'},
			{fieldtype: 'Long Text', label: 'Admission Instructions', fieldname: 'admission_instruction'}
		],
		primary_action_label: __('Order Admission'),
		primary_action : function() {
			var args = {
				patient: frm.doc.patient,
				document_type: 'Emergency Patient Record',
				admission_encounter: frm.doc.name,
				referring_practitioner: frm.doc.practitioner,
				company: frm.doc.company,
				medical_department: dialog.get_value('medical_department'),
				primary_practitioner: dialog.get_value('primary_practitioner'),
				secondary_practitioner: dialog.get_value('secondary_practitioner'),
				admission_ordered_for: dialog.get_value('admission_ordered_for'),
				admission_service_unit_type: dialog.get_value('service_unit_type'),
				expected_length_of_stay: dialog.get_value('expected_length_of_stay'),
				admission_instruction: dialog.get_value('admission_instruction')
			}
			frappe.call({
				method: 'erpnext.healthcare.doctype.emergency_patient_record.emergency_patient_record.schedule_inpatient',
				args: {
					args: args
				},
				callback: function(data) {
					if (!data.exc) {
						frm.reload_doc();
					}
				},
				freeze: true,
				freeze_message: __('Scheduling Patient Admission')
			});
			frm.refresh_fields();
			dialog.hide();
		}
	});

	dialog.set_values({
		'medical_department': frm.doc.medical_department,
		'primary_practitioner': frm.doc.practitioner,
	});

	dialog.fields_dict['service_unit_type'].get_query = function() {
		return {
			filters: {
				'inpatient_occupancy': 1,
				'allow_appointments': 0
			}
		};
	};

	dialog.show();
	dialog.$wrapper.find('.modal-dialog').css('width', '800px');
};

let create_vital_signs = function (frm) {
	if (!frm.doc.patient) {
		frappe.throw(__('Please select patient'));
	}
	frappe.route_options = {
		'patient': frm.doc.patient
		};
	frappe.new_doc('Vital Signs');
};

let create_medico_legal_record = function (frm) {
	if (!frm.doc.patient) {
		frappe.throw(__('Please select patient'));
	}
	frappe.route_options = {
		'emergency_patient_record': frm.doc.name,
		'patient': frm.doc.patient,
		'patient_name': frm.doc.patient_name,
		'blood_group': frm.doc.blood_group,
		'gender': frm.doc.gender
		};
	frappe.new_doc('Medico Legal Record');
};

let create_encounter = function (frm) {
	if (!frm.doc.patient || !frm.doc.practitioner) {
		frappe.throw(__('Please select patient and practitioner'));
	}
	frappe.route_options = {
		'patient': frm.doc.patient,
		'appointment_type': frm.doc.appointment_type,
		'practitioner': frm.doc.practitioner
		};
	frappe.new_doc('Patient Encounter');
};


let create_invoice = function(frm){
	let doc = frm.doc
	frappe.call({
		method: 'erpnext.healthcare.doctype.emergency_patient_record.emergency_patient_record.create_invoice',
		args:{
			emergency_id: doc.name
		},
		callback: function(r){
			if(!r.exc){
				frm.reload_doc();
				var doclist = frappe.model.sync(r.message);
				frappe.set_route('Form', doclist[0].doctype, doclist[0].name);
			}
		},
		freeze: true,
		freeze_message: __('Creating invoice......')
	});
}


let create_delivery_note = function(frm){
	let items = []
	let dialog = new frappe.ui.Dialog({
		title: 'Record Consumption',
		width: 100,
		fields: [
			{fieldtype: "Link", label: "Healthcare Service Unit", fieldname: "service_unit", options: "Healthcare Service Unit"},
			{fieldtype: "Column Break"},
			{fieldtype: "Link", label: "Warehouse", fieldname: "warehouse", options: "Warehouse", reqd: 1},
			{fieldtype: "Section Break"},
			{fieldtype: "Link", label: "Item", fieldname: "item", options: "Item"},
			{fieldtype: "Float", label: "Quantity", fieldname: "qty", default:1},
			{fieldtype: "Column Break"},
			{fieldtype: "Link", label: "UOM", fieldname: "uom", options:"UOM"},
			{fieldtype: "Button", label: "Add to Items", fieldname: "add_to_delivery_note"},
			{fieldtype: "Section Break"},
			{fieldtype: "HTML", label: "Item Details", fieldname: "item_details"}
		],
		primary_action_label: __("Consume"),
		primary_action : function(){
			if(items && items.length > 0){
				frappe.call({
					method: 'erpnext.healthcare.doctype.emergency_patient_record.emergency_patient_record.create_delivery_note',
					args:{
						'emergency_patient_record': frm.doc.name,
						'items': items
					},
					callback: function(data) {
						if(!data.exc){
							frm.reload_doc();
						}
					},
					freeze: true,
					freeze_message: "Creating Delivery Note"
				});
				dialog.hide();
			}
			else {
				frappe.msgprint(__("Please select atleast one item to Consume"));
			}
		}
	});
	dialog.set_values({
		'service_unit': frm.doc.service_unit,
	});
	dialog.fields_dict["item"].get_query = function(){
		return {
			filters: {
				"is_stock_item": 1,
				"disabled": ["!=", 1]
			}
		};
	};
	dialog.fields_dict["service_unit"].get_query = function(){
		return {
			filters: {
				"is_group": ["!=", 1]
			}
		};
	};
	dialog.fields_dict["warehouse"].get_query = function(){
		return {
			filters: {
				"is_group": ["!=", 1]
			}
		};
	};
	dialog.fields_dict["service_unit"].df.onchange = () => {
		frappe.call({
			method: 'frappe.client.get_value',
			args:{
				doctype: 'Healthcare Service Unit',
				fieldname: 'warehouse',
				filters:{
					'name': dialog.get_value('service_unit')
				}
			},
			callback: function(r) {
				if(r.message && r.message.warehouse){
					dialog.set_values({
						'warehouse': r.message.warehouse
					});
				}
			}
		});
	}
	dialog.fields_dict["item"].df.onchange = () => {
		if(dialog.get_value('item')){
			frappe.call({
				method: 'erpnext.healthcare.utils.sales_item_details_for_healthcare_doc',
				args:{
					item_code: dialog.get_value('item'),
					doc: frm.doc,
				},
				callback: function(r) {
					if(r.message){
						dialog.set_values({
							'uom': r.message.stock_uom
						});
					}
				}
			});
		}
	}
	dialog.fields_dict["add_to_delivery_note"].df.click = () => {
		items = update_items(items, {'service_unit': dialog.get_value('service_unit'),
		'item': dialog.get_value('item'),
		'qty': dialog.get_value('qty'),
		'warehouse': dialog.get_value('warehouse'),
		'uom': dialog.get_value('uom')});
		var $wrapper = dialog.fields_dict.item_details.$wrapper;
		$wrapper
			.html(consumssion_details_html(items));
		dialog.set_values({
			'item': '',
			'uom': '',
			'qty': 1
		});
	}
	dialog.show();
};

var consumssion_details_html = function(items) {
	var table_html = `<div class='col-md-12 col-sm-12 text-muted'><table class="table table-condensed bordered">
	<tr>
		<th>Item</th><th>Quantity</th><th>UOM</th><th>Warehouse</th><th>Healthcare Service Unit</th>
	</tr>`;

	$.each(items, function(index, item){
		table_html += `<tr>
			<td>${item['item']}</td>
			<td>${item['qty']}</td>
			<td>${item['uom']}</td>
			<td>${item['warehouse']}</td>
			<td>${item['service_unit']}</td>
		</tr>`;
	});

	table_html += `</table> <br/> <hr/> </div>`;
	return table_html;
};

let update_items = function(items, new_item){
	if(new_item && new_item['item'] && new_item['qty'] && new_item['service_unit'] && new_item['warehouse']){
		let item_exist_in_the_list = false;
		$.each(items, function(index, item){
			if(item['item'] == new_item['item']){
				item['qty'] = new_item['qty'];
				item['uom'] = new_item['uom'];
				item['service_unit'] = new_item['service_unit'];
				item['warehouse'] = new_item['warehouse'];
				item_exist_in_the_list = true;
			}
		});
		if(!item_exist_in_the_list){
			items.push(new_item);
		}
	}
	return items;
};
