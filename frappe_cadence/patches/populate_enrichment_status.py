import frappe

def execute():
    statuses = [
        {"status": "Pending", "color": "gray"},
        {"status": "Processing", "color": "blue"},
        {"status": "Enriched", "color": "green"},
        {"status": "Partial", "color": "yellow"},
        {"status": "Stale", "color": "orange"},
        {"status": "Failed", "color": "red"}
    ]

    for status in statuses:
        if not frappe.db.exists("Enrichment Status", status["status"]):
            doc = frappe.new_doc("Enrichment Status")
            doc.update(status)
            doc.insert(ignore_permissions=True)
