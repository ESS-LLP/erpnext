
frappe.listview_settings['Clinical Procedure'] = {
onload: function(listview) {
  listview.page.add_menu_item(__("Create Multiple"), function() {
    create_multiple_dialog(listview);
  });
}
};


var create_multiple_dialog = function(listview){
  var dialog = new frappe.ui.Dialog({
		title: 'Create Multiple Clinical Procedure',
		width: 100,
		fields: [
			{fieldtype: "Link", label: "Patient", fieldname: "patient", options: "Patient", reqd: 1},
			{fieldtype: "Link", label: "Patient Encounter", fieldname: "patient_encounter", options: "Patient Encounter", reqd: 1,
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
    primary_action_label: __("Create Clinical Procedure"),
		primary_action : function(){
			frappe.call({
				method: 'erpnext.healthcare.doctype.clinical_procedure.clinical_procedure.create_multiple',
				args:{
					'docname': dialog.get_value("patient_encounter")
				},
				callback: function(data) {
					if(!data.exc){
						if(!data.message){
							frappe.msgprint(__("No Clinical Procedure created"))
						}
						listview.refresh();
					}
				},
				freeze: true,
				freeze_message: "Creating Clinical Procedure..."
			});
			dialog.hide();
		}
	});
	dialog.show();
}
