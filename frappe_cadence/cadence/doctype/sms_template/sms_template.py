import frappe
from frappe.model.document import Document

class SMSTemplate(Document):
    def on_update(self):
        cadences = frappe.get_all("Multi Channel Cadence", filters={"status": ["in", ["Scheduled", "In Progress"]]}, fields=["name", "cadence_name"])
        for camp in cadences:
            master_cadence = frappe.get_doc("Cadence", camp.cadence_name)
            for schedule in master_cadence.cadence_schedules:
                if schedule.reference_doctype == "SMS Template" and schedule.reference_name == self.name:
                    doc = frappe.get_doc("Multi Channel Cadence", camp.name)
                    doc.save(ignore_permissions=True)
                    break
