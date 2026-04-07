import frappe
import json

@frappe.whitelist()
def get(filters=None, fields=None, limit=None):
    if isinstance(filters, str):
        filters = json.loads(filters)
    if isinstance(fields, str):
        fields = json.loads(fields)
        
    if not filters:
        filters = []
    if not fields:
        fields = ["name"]
        
    limit_kwargs = {}
    if limit is not None:
        try:
            limit_kwargs["limit"] = int(limit)
        except ValueError:
            pass
        
    standard_filters = []
    excluded_campaigns = []
    
    if isinstance(filters, dict):
        # We need to process dot notation for dict filters as well
        new_filters = []
        for key, value in filters.items():
            if "." in key:
                link_fieldname, target_fieldname = key.split(".", 1)
                meta = frappe.get_meta("CRM Lead")
                field_def = meta.get_field(link_fieldname)
                if field_def and field_def.fieldtype in ("Link", "Dynamic Link") and field_def.options:
                    target_doctype = field_def.options
                    if isinstance(value, list) and len(value) == 2:
                        target_op, target_val = value[0], value[1]
                    else:
                        target_op, target_val = "=", value
                        
                    target_records = frappe.get_all(
                        target_doctype,
                        filters={target_fieldname: (target_op, target_val)},
                        pluck="name"
                    )
                    if target_records:
                        new_filters.append(["CRM Lead", link_fieldname, "in", target_records])
                    else:
                        new_filters.append(["CRM Lead", link_fieldname, "in", ["__NON_EXISTENT__"]])
                else:
                    new_filters.append(["CRM Lead", key, "=", value])
            else:
                if isinstance(value, list) and len(value) == 2:
                    new_filters.append(["CRM Lead", key, value[0], value[1]])
                else:
                    new_filters.append(["CRM Lead", key, "=", value])
        filters = new_filters

    if isinstance(filters, list):
        for f in filters:
            if isinstance(f, list) and len(f) >= 3:
                # Parse Frappe's filter format
                doctype = f[0] if len(f) == 4 else None
                fieldname = f[1] if len(f) == 4 else f[0]
                operator = f[2] if len(f) == 4 else f[1]
                value = f[3] if len(f) == 4 else f[2]
                
                # Intercept the CRM Lead Campaign exclusion filter
                # We ignore fieldname (whether it is 'name' or 'campaign_name')
                # and assume the value contains the campaign IDs to exclude.
                if doctype == "CRM Lead Campaign" and operator.lower() in ("not in", "!="):
                    if isinstance(value, list):
                        excluded_campaigns.extend(value)
                    else:
                        excluded_campaigns.append(value)
                    continue
                    
                if "." in fieldname:
                    link_fieldname, target_fieldname = fieldname.split(".", 1)
                    base_doctype = doctype or "CRM Lead"
                    meta = frappe.get_meta(base_doctype)
                    field_def = meta.get_field(link_fieldname)
                    
                    if field_def and field_def.fieldtype in ("Link", "Dynamic Link") and field_def.options:
                        target_doctype = field_def.options
                        
                        target_records = frappe.get_all(
                            target_doctype,
                            filters={target_fieldname: (operator, value)},
                            pluck="name"
                        )
                        
                        if target_records:
                            standard_filters.append([base_doctype, link_fieldname, "in", target_records])
                        else:
                            standard_filters.append([base_doctype, link_fieldname, "in", ["__NON_EXISTENT__"]])
                        continue
                        
            standard_filters.append(f)
            
    if excluded_campaigns:
        campaign_leads = frappe.get_all(
            "CRM Lead Campaign", 
            filters={"campaign_name": ("in", excluded_campaigns)}, 
            pluck="parent"
        )
        if campaign_leads:
            standard_filters.append(["name", "not in", campaign_leads])
            
    # Fetch leads using standard Frappe logic
    leads = frappe.get_all("CRM Lead", filters=standard_filters, fields=fields, **limit_kwargs)
            
    return leads
