import frappe
from teraoka_integration.teraoka_integration.netsuite import push_to_erp

settings = frappe.get_single("Teraoka Settings")
print(f"DEBUG: NetSuite Enabled = {settings.netsuite_enabled}")
print(f"DEBUG: Account ID = {settings.netsuite_account_id}")
print(f"DEBUG: REST URL = {settings.netsuite_rest_url}")

invoice = frappe.get_all("Sales Invoice", limit=1, order_by="creation desc")
if not invoice:
    print("ERROR: No Sales Invoices found to test.")
else:
    invoice_name = invoice[0].name
    print(f"DEBUG: Attempting push for {invoice_name}...")
    try:
        result = push_to_erp(invoice_name)
        print(f"FINAL_RESULT: {result}")
    except Exception as e:
        print(f"CRITICAL ERROR during push: {e}")
