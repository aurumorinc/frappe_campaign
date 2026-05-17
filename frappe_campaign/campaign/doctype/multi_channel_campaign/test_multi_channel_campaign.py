import frappe
from frappe.tests import IntegrationTestCase
from unittest.mock import patch, call
import json

class TestMultiChannelCampaign(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create necessary doctypes if they don't exist for testing
        if not frappe.db.exists("DocType", "FS Job"):
            doc = frappe.get_doc({
                "doctype": "DocType",
                "name": "FS Job",
                "module": "Core",
                "custom": 1,
                "fields": [
                    {"fieldname": "status", "fieldtype": "Data", "label": "Status"},
                    {"fieldname": "arguments", "fieldtype": "Code", "label": "Arguments"},
                    {"fieldname": "job_type", "fieldtype": "Data", "label": "Job Type"}
                ]
            })
            doc.insert(ignore_permissions=True)
            
        if not frappe.db.exists("Controller Job Type", "frappe_campaign.campaign.agent.process_campaign_step"):
            if not frappe.db.exists("DocType", "Controller Job Type"):
                doc = frappe.get_doc({
                    "doctype": "DocType",
                    "name": "Controller Job Type",
                    "module": "Core",
                    "custom": 1,
                    "fields": [
                        {"fieldname": "method", "fieldtype": "Data", "label": "Method"}
                    ]
                })
                doc.insert(ignore_permissions=True)
            
            frappe.get_doc({
                "doctype": "Controller Job Type",
                "name": "frappe_campaign.campaign.agent.process_campaign_step",
                "method": "frappe_campaign.campaign.agent.process_campaign_step"
            }).insert(ignore_permissions=True)
            
        # Create templates
        for dt in ["Email Template", "LinkedIn Template", "SMS Template"]:
            name = f"Test {dt}"
            if not frappe.db.exists(dt, name):
                if dt == "Email Template":
                    doc = frappe.get_doc({
                        "doctype": dt,
                        "name": name,
                        "subject": "Test Subject",
                        "response": "Test Content",
                        "status": "Enabled"
                    })
                else:
                    doc = frappe.get_doc({
                        "doctype": dt,
                        "name": name,
                        "title": name,
                        "status": "Enabled"
                    })
                doc.insert(ignore_permissions=True)
                
        lead = frappe.get_all("CRM Lead", limit=1)
        if not lead:
            lead_doc = frappe.get_doc({
                "doctype": "CRM Lead",
                "first_name": "Test",
                "last_name": "Lead"
            }).insert(ignore_permissions=True)
            cls.lead_name = lead_doc.name
        else:
            cls.lead_name = lead[0].name
            
        frappe.db.commit()

    def setUp(self):
        frappe.db.rollback()
        
        # Create a master Campaign
        self.master_campaign = frappe.get_doc({
            "doctype": "Campaign",
            "campaign_name": "_Test Master Campaign",
            "campaign_schedules": [
                {"reference_doctype": "Email Template", "reference_name": "Test Email Template", "send_after_days": 1},
                {"reference_doctype": "LinkedIn Template", "reference_name": "Test LinkedIn Template", "send_after_days": 2},
                {"reference_doctype": "SMS Template", "reference_name": "Test SMS Template", "send_after_days": 3}
            ]
        }).insert(ignore_permissions=True)
        
        # Create a dummy campaign
        self.campaign = frappe.get_doc({
            "doctype": "Multi Channel Campaign",
            "campaign_name": self.master_campaign.name,
            "campaign_for": "CRM Lead",
            "recipient": self.lead_name,
            "start_date": "2024-01-01",
            "status": "Scheduled"
        })

    @patch("frappe_campaign.campaign.doctype.multi_channel_campaign.multi_channel_campaign.enqueue")
    def test_on_update_cancels_existing_jobs(self, mock_enqueue):
        self.campaign.insert(ignore_permissions=True)
        mock_enqueue.reset_mock()
        
        # Create dummy FS Jobs
        job1 = frappe.get_doc({
            "doctype": "FS Job",
            "status": "queued",
            "job_type": "frappe_campaign.campaign.agent.process_campaign_step",
            "arguments": json.dumps({"campaign_name": self.campaign.name})
        }).insert(ignore_permissions=True)
        
        job2 = frappe.get_doc({
            "doctype": "FS Job",
            "status": "started",
            "job_type": "frappe_campaign.campaign.agent.process_campaign_step",
            "arguments": json.dumps({"campaign_name": self.campaign.name})
        }).insert(ignore_permissions=True)
        
        # Trigger on_update
        self.campaign.on_update()
        
        # Assert jobs are cancelled
        self.assertEqual(frappe.db.get_value("FS Job", job1.name, "status"), "canceled")
        self.assertEqual(frappe.db.get_value("FS Job", job2.name, "status"), "canceled")

    @patch("frappe_campaign.campaign.doctype.multi_channel_campaign.multi_channel_campaign.enqueue")
    def test_on_update_enqueues_all_steps_initially(self, mock_enqueue):
        self.campaign.insert(ignore_permissions=True)
        mock_enqueue.reset_mock()
        self.campaign.on_update()
        
        self.assertEqual(mock_enqueue.call_count, 3)
        
        calls = [
            call("frappe_campaign.campaign.agent.process_campaign_step", queue="default", campaign_name=self.campaign.name, schedule_name=self.master_campaign.campaign_schedules[0].name, previous_schedule_name=None),
            call("frappe_campaign.campaign.agent.process_campaign_step", queue="default", campaign_name=self.campaign.name, schedule_name=self.master_campaign.campaign_schedules[1].name, previous_schedule_name=self.master_campaign.campaign_schedules[0].name),
            call("frappe_campaign.campaign.agent.process_campaign_step", queue="default", campaign_name=self.campaign.name, schedule_name=self.master_campaign.campaign_schedules[2].name, previous_schedule_name=self.master_campaign.campaign_schedules[1].name)
        ]
        mock_enqueue.assert_has_calls(calls)

    @patch("frappe_campaign.campaign.doctype.multi_channel_campaign.multi_channel_campaign.enqueue")
    def test_on_update_skips_sent_communications(self, mock_enqueue):
        self.campaign.insert(ignore_permissions=True)
        mock_enqueue.reset_mock()
        
        # Create a Sent Communication for schedule 1
        frappe.get_doc({
            "doctype": "Communication",
            "communication_medium": "Email",
            "subject": "Test",
            "reference_doctype": "Multi Channel Campaign",
            "reference_name": self.campaign.name,
            "campaign_schedule_reference": self.master_campaign.campaign_schedules[0].name,
            "delivery_status": "Sent"
        }).insert(ignore_permissions=True)
        
        self.campaign.on_update()
        
        # Should only enqueue for schedule 2 and 3
        self.assertEqual(mock_enqueue.call_count, 2)
        
        calls = [
            call("frappe_campaign.campaign.agent.process_campaign_step", queue="default", campaign_name=self.campaign.name, schedule_name=self.master_campaign.campaign_schedules[1].name, previous_schedule_name=self.master_campaign.campaign_schedules[0].name),
            call("frappe_campaign.campaign.agent.process_campaign_step", queue="default", campaign_name=self.campaign.name, schedule_name=self.master_campaign.campaign_schedules[2].name, previous_schedule_name=self.master_campaign.campaign_schedules[1].name)
        ]
        mock_enqueue.assert_has_calls(calls)

    @patch("frappe_campaign.campaign.doctype.multi_channel_campaign.multi_channel_campaign.enqueue")
    def test_on_update_deletes_unsent_communications_and_requeues(self, mock_enqueue):
        self.campaign.insert(ignore_permissions=True)
        mock_enqueue.reset_mock()
        
        # Create a Scheduled Communication for schedule 1
        comm = frappe.get_doc({
            "doctype": "Communication",
            "communication_medium": "Email",
            "subject": "Test",
            "reference_doctype": "Multi Channel Campaign",
            "reference_name": self.campaign.name,
            "campaign_schedule_reference": self.master_campaign.campaign_schedules[0].name,
            "delivery_status": "Scheduled"
        }).insert(ignore_permissions=True)
        
        self.campaign.on_update()
        
        # Assert Communication is deleted
        self.assertFalse(frappe.db.exists("Communication", comm.name))
        
        # Should enqueue for all 3 schedules
        self.assertEqual(mock_enqueue.call_count, 3)
