frappe.listview_settings["Communication"] = frappe.listview_settings["Communication"] || {};

// Monkey patch: Remove the hardcoded CommunicationComposer override
// This restores the default "Add Communication" button behavior
// which opens the standard DocType form.
frappe.listview_settings["Communication"].primary_action = null;
