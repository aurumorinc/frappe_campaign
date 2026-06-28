import frappe

def sync_lead_cadence(doc, method):
	"""Update the hidden 'cadences' child table on CRM Lead for filtering purposes"""
	if doc.email_cadence_for == "CRM Lead":
		if not frappe.db.exists("CRM Lead", doc.recipient):
			return

		lead = frappe.get_doc("CRM Lead", doc.recipient)
		
		if not hasattr(lead, "cadences"):
			return

		# Check if already exists in child table
		if not any(row.cadence_name == doc.cadence_name for row in lead.cadences):
			lead.append("cadences", {
				"cadence_name": doc.cadence_name
			})
			lead.save(ignore_permissions=True)

def remove_lead_cadence(doc, method):
	"""Remove the reference from CRM Lead when an Email Cadence is deleted"""
	if doc.email_cadence_for == "CRM Lead":
		if not frappe.db.exists("CRM Lead", doc.recipient):
			return

		lead = frappe.get_doc("CRM Lead", doc.recipient)
		if not hasattr(lead, "cadences"):
			return

		# Since we don't have the email_cadence link anymore, 
		# we should check if any OTHER email cadences for this lead and cadence still exist
		other_exists = frappe.db.exists("Email Cadence", {
			"cadence_name": doc.cadence_name,
			"recipient": doc.recipient,
			"name": ("!=", doc.name)
		})

		if not other_exists:
			lead.set("cadences", [
				row for row in lead.cadences if row.cadence_name != doc.cadence_name
			])
			lead.save(ignore_permissions=True)
