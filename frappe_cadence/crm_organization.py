import frappe
import json
from frappe_cadence.crm_lead import get as get_crm_leads

@frappe.whitelist()
def get(filters=None, fields=None, limit=None):
    """
    Fetches leads matching the `filters` criteria, 
    and returns the unique organizations for those leads.
    """
    # Parse the incoming fields from JSON string
    if isinstance(fields, str):
        fields = json.loads(fields)
        
    if not fields:
        fields = ["name"]
        
    limit_val = None
    if limit is not None:
        try:
            limit_val = int(limit)
        except ValueError:
            pass
        
    # We use our custom get_crm_leads method to fetch the leads with 'organization'
    # By passing the 'filters', it handles standard lead filters plus our custom 'exclude_cadence'.
    # We set limit=0 to get ALL matching leads, so we can group their organizations accurately.
    leads = get_crm_leads(filters=filters, fields=["organization"], limit=0)
    
    # Extract unique organizations
    org_names = list(set([lead.get("organization") for lead in leads if lead.get("organization")]))
    
    if not org_names:
        return []
        
    # Apply the limit to the unique organizations list
    if limit_val and limit_val > 0:
        org_names = org_names[:limit_val]
        
    # Fetch the actual organization records
    organizations = frappe.get_all(
        "CRM Organization", 
        filters={"name": ("in", org_names)}, 
        fields=fields
    )
    
    return organizations
