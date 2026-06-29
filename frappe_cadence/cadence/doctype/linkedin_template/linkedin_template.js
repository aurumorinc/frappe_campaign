frappe.ui.form.on("LinkedIn Template", {
	refresh: function(frm) {
		frm.add_custom_button(__("Optimize"), function() {
			frappe.msgprint(__("Not implemented"));
		});
		frm.add_custom_button(__("Process"), function() {
			frappe.msgprint(__("Not implemented"));
		});
	}
});
