import frappe
import requests
import json
import time
import uuid
import hmac
import hashlib
import base64
from urllib.parse import quote, urlencode

class NetSuiteConnector:
    def __init__(self, settings):
        self.settings = settings
        self.account_id = settings.netsuite_account_id
        self.consumer_key = settings.ns_consumer_key
        self.consumer_secret = settings.ns_consumer_secret
        self.token_id = settings.ns_token_id
        self.token_secret = settings.ns_token_secret
        self.base_url = settings.netsuite_rest_url

    def get_auth_header(self, method, url):
        """Generates the OAuth 1.0 Authorization header for NetSuite TBA."""
        params = {
            'oauth_consumer_key': self.consumer_key,
            'oauth_token': self.token_id,
            'oauth_nonce': uuid.uuid4().hex,
            'oauth_timestamp': str(int(time.time())),
            'oauth_signature_method': 'HMAC-SHA256',
            'oauth_version': '1.0'
        }
        
        # Base string for signature
        base_string = f"{method.upper()}&{quote(url, safe='')}&{quote(urlencode(sorted(params.items()), quote_via=quote), safe='')}"
        key = f"{quote(self.consumer_secret, safe='')}&{quote(self.token_secret, safe='')}"
        
        signature = base64.b64encode(
            hmac.new(key.encode(), base_string.encode(), hashlib.sha256).digest()
        ).decode()
        
        params['oauth_signature'] = signature
        
        # NetSuite TBA requires realm to be uppercase with underscores (e.g. 1234567_SB1)
        params['realm'] = self.account_id.upper().replace("-", "_")
        
        auth_header = "OAuth " + ", ".join([f'{k}="{quote(v, safe="")}"' for k, v in sorted(params.items())])
        return auth_header

    def push_invoice(self, invoice_doc):
        """Pushes an ERPNext Sales Invoice to NetSuite."""
        if not self.settings.netsuite_enabled:
            return {"status": "Skipped", "message": "NetSuite Sync Disabled"}

        payload = self.prepare_payload(invoice_doc)
        headers = {
            "Authorization": self.get_auth_header("POST", self.base_url),
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(self.base_url, data=json.dumps(payload), headers=headers)
            res_data = response.json()
            
            if response.status_code in [200, 201]:
                ns_id = res_data.get("internalId") or res_data.get("id")
                if ns_id:
                    invoice_doc.db_set("netsuite_id", ns_id)
                    return {"status": "Success", "ns_id": ns_id}
            
            error_msg = res_data.get("error", {}).get("message") or response.text
            frappe.log_error(title=f"NetSuite Push Failed: {invoice_doc.name}", message=error_msg)
            return {"status": "Failed", "error": error_msg}
            
        except Exception as e:
            frappe.log_error(title="NetSuite Connection Error", message=frappe.get_traceback())
            return {"status": "Failed", "error": str(e)}

    def prepare_payload(self, doc):
        """Maps ERPNext Invoice fields to NetSuite Sales Order/Invoice format."""
        # Retrieve NetSuite Location ID from Shop Mapping
        ns_location_id = None
        if doc.teraoka_shop_code:
            ns_location_id = frappe.db.get_value("Teraoka Shop Mapping Details", 
                {"shop_code": doc.teraoka_shop_code}, "netsuite_location_id")

        items = []
        for item in doc.items:
            items.append({
                "item": {"id": item.item_code},
                "quantity": item.qty,
                "rate": item.rate,
                "location": {"id": ns_location_id} if ns_location_id else None
            })
            
        payload = {
            "entity": {"id": doc.customer}, # NetSuite Customer Internal ID
            "trandate": str(doc.posting_date),
            "externalId": doc.name,
            "location": {"id": ns_location_id} if ns_location_id else None,
            "memo": f"Teraoka POS Sync | Shop: {doc.teraoka_shop_code or 'N/A'}",
            "item": {"items": items}
        }
        
        return payload

def push_to_erp(invoice_name):
    """Entry point for NetSuite synchronization."""
    settings = frappe.get_single("Teraoka Settings")
    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    
    connector = NetSuiteConnector(settings)
    return connector.push_invoice(invoice)

def retry_failed_netsuite_syncs():
    """
    Background task to retry synchronizing orphaned invoices.
    Scans for submitted invoices with missing NetSuite IDs from the last 48 hours.
    """
    from frappe.utils import add_days, nowdate
    
    settings = frappe.get_single("Teraoka Settings")
    if not settings.netsuite_enabled:
        return
        
    threshold_date = add_days(nowdate(), -2)
    
    orphaned_invoices = frappe.get_all("Sales Invoice", filters={
        "docstatus": 1,
        "netsuite_id": ["in", ["", None]],
        "posting_date": [">=", threshold_date],
        "company": settings.company
    }, fields=["name"])
    
    if not orphaned_invoices:
        return
        
    for inv in orphaned_invoices:
        try:
            push_to_erp(inv.name)
        except Exception:
            continue

@frappe.whitelist()
def send_to_netsuite():
    """
    Scheduled job to push all 'Pending Sync' Teraoka File Logs to NetSuite.
    """
    settings = frappe.get_single("Teraoka Settings")
    if not settings.netsuite_enabled:
        return
        
    logs = frappe.get_all("Teraoka File Log", filters={"status": "Pending Sync"}, fields=["name"])
    for log_meta in logs:
        frappe.enqueue(
            "teraoka_integration.teraoka_integration.services.netsuite.sync_log_to_netsuite",
            queue="default",
            log_name=log_meta.name,
            timeout=1500
        )

def sync_log_to_netsuite(log_name):
    """
    Background Job to sync a specific File Log to NetSuite and send Teams webhook.
    """
    log = frappe.get_doc("Teraoka File Log", log_name)
    settings = frappe.get_single("Teraoka Settings")
    
    invoices = frappe.get_all("Sales Invoice", filters={
        "docstatus": 1,
        "teraoka_shop_code": log.shop_code,
        "posting_date": log.file_date,
        "company": settings.company,
        "netsuite_id": ["in", ["", None]]
    }, fields=["name"])
    
    success_count = 0
    error_count = 0
    errors = []
    
    for inv in invoices:
        res = push_to_erp(inv.name)
        if res.get("status") == "Success":
            success_count += 1
        else:
            error_count += 1
            errors.append(res.get("error"))
            
    # Update File Log status
    if error_count == 0 and success_count == len(invoices):
        log.status = "Success"
    elif success_count > 0 and error_count > 0:
        log.status = "Partial Success"
    else:
        log.status = "Failed"
        
    if errors:
        log.logs = (log.logs or "") + "\\n" + "\\n".join(errors)
        
    log.save(ignore_permissions=True)
    frappe.db.commit()
    
    # Send Webhook Notification
    if settings.teams_webhook_url:
        send_teams_notification(log, settings.teams_webhook_url)
        
    # Archive file if enabled
    if log.status in ("Success", "Partial Success") and settings.archive_processed_files:
        try:
            from .ftp import archive_file, TeraokaConnector
            with TeraokaConnector(settings) as tconn:
                archive_file(settings, log.filename, conn_obj=tconn)
        except Exception as e:
            frappe.logger("teraoka").error(f"Failed to archive file {log.filename}: {e}")

def send_teams_notification(log, webhook_url):
    """Sends a summary notification to MS Teams."""
    import requests
    import json
    
    color = "00FF00" if log.status == "Success" else ("FFFF00" if log.status == "Partial Success" else "FF0000")
    
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": color,
        "summary": f"Teraoka Sync: {log.filename}",
        "sections": [{
            "activityTitle": f"Teraoka Integration: NetSuite Sync {log.status}",
            "activitySubtitle": f"File: {log.filename}",
            "facts": [
                {"name": "Shop Code", "value": str(log.shop_code)},
                {"name": "Transaction Date", "value": str(log.file_date)},
                {"name": "Total Amount", "value": str(log.total_amount)},
                {"name": "Status", "value": log.status}
            ],
            "markdown": True
        }]
    }
    
    try:
        requests.post(webhook_url, json=payload, timeout=10)
    except Exception as e:
        frappe.logger("teraoka").error(f"Teams webhook failed: {str(e)}")
