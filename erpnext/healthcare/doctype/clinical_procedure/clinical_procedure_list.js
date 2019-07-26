
frappe.listview_settings['Clinical Procedure'] = {
onload: function(listview) {
  listview.page.add_menu_item(__("Create Multiple"), function() {
    create_multiple_dialog(listview);
  });
}
};


var create_multiple_dialog = function(listview){
  var dialog = new frappe.ui.Dialog({
		title: 'Create Multiple Lab Test',
		width: 100,
		fields: [
			{fieldtype: "Link", label: "Patient", fieldname: "patient", options: "Patient", reqd: 1},
			{fieldtype: "Link", fieldname: "docname", options: "Patient Encounter", reqd: 1,
				get_query: function(){
					return {
						filters: {
							"patient": dialog.get_value("patient"),
							"docstatus": ["<", 2]
						}
					};
				}
			}
		],
    primary_action_label: __("Create Lab Test"),
		primary_action : function(){
			frappe.call({
				method: 'erpnext.healthcare.doctype.clinical_procedure.clinical_procedure.create_multiple',
				args:{
					'docname': dialog.get_value("docname")
				},
				callback: function(data) {
					if(!data.exc){
						if(!data.message){
							frappe.msgprint(__("No Lab Test created"))
						}
						listview.refresh();
					}
				},
				freeze: true,
				freeze_message: "Creating Lab Test..."
			});
			dialog.hide();
		}
	});
	dialog.show();
}
