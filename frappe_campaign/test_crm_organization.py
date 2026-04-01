import frappe
from frappe.tests import IntegrationTestCase
from frappe_campaign.crm_organization import get as get_crm_organizations

class TestCRMOrganization(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # 1. Create Organizations
        cls.org1 = frappe.get_doc({
            "doctype": "CRM Organization",
            "organization_name": "_Test Org 1"
        }).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
        
        cls.org2 = frappe.get_doc({
            "doctype": "CRM Organization",
            "organization_name": "_Test Org 2"
        }).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
        
        # 2. Create Campaign
        cls.campaign1 = frappe.get_doc({
            "doctype": "Campaign",
            "campaign_name": "_Test Campaign 1"
        }).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
        
        # 3. Create Leads
        cls.lead1 = frappe.get_doc({
            "doctype": "CRM Lead",
            "first_name": "Test Lead 1",
            "source": "Cold Email",
            "email": "test1@example.com",
            "organization": cls.org1.name
        }).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
        
        cls.lead2 = frappe.get_doc({
            "doctype": "CRM Lead",
            "first_name": "Test Lead 2",
            "source": "Cold Email",
            "email": "test2@example.com",
            "organization": cls.org2.name
        }).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
        
        cls.lead3 = frappe.get_doc({
            "doctype": "CRM Lead",
            "first_name": "Test Lead 3",
            "source": "Website",
            "email": "test3@example.com",
            "organization": cls.org2.name
        }).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
        
        # 4. Link Lead 1 to Campaign 1
        frappe.get_doc({
            "doctype": "CRM Lead Campaign",
            "parent": cls.lead1.name,
            "parenttype": "CRM Lead",
            "parentfield": "campaigns",
            "campaign_name": cls.campaign1.name
        }).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

    @classmethod
    def tearDownClass(cls):
        frappe.db.rollback()
        super().tearDownClass()

    def test_get_organizations(self):
        filters = '[["CRM Lead", "source", "=", "Cold Email"]]'
        fields = '["name", "organization_name"]'
        
        orgs = get_crm_organizations(filters=filters, fields=fields)
        
        # Should return both org1 and org2 because lead1 (org1) and lead2 (org2) match
        org_names = [o.name for o in orgs]
        self.assertIn(self.org1.name, org_names)
        self.assertIn(self.org2.name, org_names)

    def test_get_organizations_with_campaign_exclusion(self):
        filters = f'[["CRM Lead Campaign", "name", "not in", ["{self.campaign1.name}"]], ["CRM Lead", "source", "=", "Cold Email"]]'
        fields = '["name", "organization_name"]'
        
        orgs = get_crm_organizations(filters=filters, fields=fields)
        
        # lead1 is excluded, so org1 should not be returned (unless another lead from org1 is in the results, which is not the case)
        org_names = [o.name for o in orgs]
        self.assertNotIn(self.org1.name, org_names)
        self.assertIn(self.org2.name, org_names)

    def test_get_organizations_with_limit(self):
        filters = '[["CRM Lead", "source", "=", "Cold Email"]]'
        fields = '["name", "organization_name"]'
        
        orgs = get_crm_organizations(filters=filters, fields=fields, limit=1)
        self.assertEqual(len(orgs), 1)
