frappe.ui.form.on("WhatsApp Template", {
	refresh: function(frm) {
		frm.add_custom_button(__("Optimize"), function() {
			frappe.msgprint(__("Not implemented"));
		});
		frm.add_custom_button(__("Process"), function() {
			frappe.msgprint(__("Not implemented"));
		});
	}
});
