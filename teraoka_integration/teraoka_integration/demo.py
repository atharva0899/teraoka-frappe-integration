import frappe
from frappe.utils import now_datetime, add_days

def create_demo_data():
    # 1. Remove existing records
    frappe.db.delete("Teraoka File Log")
    
    # 2. Create new demo data
    logs = [
        {
            "filename": "POS_SALES_SHOP01_20240328.csv",
            "status": "Success",
            "processed_on": add_days(now_datetime(), -2),
            "logs": "Fetched 150 items. Generated Sales Invoice SINV-001."
        },
        {
            "filename": "POS_SALES_SHOP02_20240329.csv",
            "status": "Success",
            "processed_on": add_days(now_datetime(), -1),
            "logs": "Fetched 85 items. Generated Sales Invoice SINV-002."
        },
        {
            "filename": "POS_SALES_SHOP01_20240330.csv",
            "status": "Failed",
            "processed_on": now_datetime(),
            "logs": "Attempted connection to 89.167.12.180. Failed after 3 retries: Connection Timeout."
        }
    ]
    
    for log in logs:
        doc = frappe.get_doc({
            "doctype": "Teraoka File Log",
            **log
        })
        doc.insert(ignore_permissions=True)
    
    frappe.db.commit()
    return "Demo data created."
