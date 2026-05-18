import frappe
from frappe.model.document import Document
from frappe_controller.utils.background_jobs import enqueue

class MultiChannelCampaign(Document):
    def on_update(self):
        # Detect if the campaign steps or linked templates have changed.
        # If changed (or if newly created and Scheduled):
        if self.status in ["Scheduled", "In Progress"]:
            # Cancel Existing Jobs
            jobs = frappe.get_all("FS Job", filters={"status": ["in", ["queued", "started"]]}, fields=["name", "arguments"])
            for job in jobs:
                import json
                try:
                    kwargs = json.loads(job.arguments)
                    if kwargs.get("campaign_name") == self.name:
                        frappe.db.set_value("FS Job", job.name, "status", "canceled")
                except Exception:
                    pass
            
            # Enqueue New Jobs
            # Fetch the master Campaign to get the schedules
            campaign = frappe.get_doc("Campaign", self.campaign_name)
            
            for idx, schedule in enumerate(campaign.campaign_schedules):
                # Check if a Communication record exists for this campaign_name and schedule_name
                comm = frappe.get_all("Communication", filters={
                    "reference_doctype": "Multi Channel Campaign",
                    "reference_name": self.name,
                    "campaign_schedule": schedule.name
                }, fields=["name", "delivery_status"])
                
                if comm:
                    if comm[0].delivery_status == "Sent":
                        continue # Skip this schedule
                    else:
                        frappe.delete_doc("Communication", comm[0].name)
                
                previous_schedule_name = campaign.campaign_schedules[idx - 1].name if idx > 0 else None
                
                enqueue(
                    "frappe_campaign.campaign.agent.process_campaign_step",
                    queue="default",
                    campaign_name=self.name,
                    schedule_name=schedule.name,
                    previous_schedule_name=previous_schedule_name
                )
