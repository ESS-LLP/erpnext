
var item_action_buttons = function(frm) {
	if(!frm.doc.__islocal) {
		frm.add_custom_button(__('Change Item Code'), function() {
			change_item_code(frm);
		} );
		if(frm.doc.disabled == 1){
			frm.add_custom_button(__('Enable'), function() {
				enable_disable_template(frm, 0);
			} );
		}
		else{
			frm.add_custom_button(__('Disable'), function() {
				enable_disable_template(frm, 1);
			} );
		}
	}
}

var enable_disable_template = function(frm, disabled){
	frappe.call({
		method: "erpnext.healthcare.utils.disable_enable_template",
		args: {doctype: "Radiology Procedure", docname: frm.doc.name, 'item_code': frm.doc.item || frm.doc.item_code, disabled: disabled},
		callback: function(){
			frm.reload_doc();
		}
	});
};

var change_item_code = function(frm){
	var doc = frm.doc;
	var d = new frappe.ui.Dialog({
		title:__("Change Item Code"),
		fields:[
			{
				"fieldtype": "Data",
				"label": "Item Code",
				"fieldname": "item_code",
				reqd:1
			},
			{
				"fieldtype": "Button",
				"label": __("Change Code"),
				click: function() {
					var values = d.get_values();
					if(!values)
						return;
					change_item_code_from_doc(values["item_code"], doc);
					d.hide();
				}
			}
		]
	});
	d.show();
	d.set_values({
		'item_code': doc.item_code
	});
};

var change_item_code_from_doc = function(item_code, doc){
	frappe.call({
		"method": "erpnext.healthcare.utils.change_item_code_from_doc",
		"args": {item_code: item_code, doc: doc},
		callback: function () {
			cur_frm.reload_doc();
			frappe.show_alert({
				message: __("Item Code renamed successfully"),
				indicator: "green"
			});
		},
		freeze: true,
		freeze_message: __("Changing Item Code...")
	});
};
