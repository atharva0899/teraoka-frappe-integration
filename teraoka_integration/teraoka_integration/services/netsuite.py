import frappe
import requests
from .google_chat import send_google_chat_notification
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
        self.consumer_secret = settings.get_password("ns_consumer_secret")
        self.token_id = settings.ns_token_id
        self.token_secret = settings.get_password("ns_token_secret")
        self.base_url = settings.netsuite_rest_url

    def _request(self, method, url, **kwargs):
        """Executes a request to NetSuite under a distributed lock to prevent concurrency issues."""
        lock = frappe.cache().lock("netsuite_api_concurrency_lock", timeout=120, blocking_timeout=120)
        with lock:
            import time
            time.sleep(0.2)
            return requests.request(method, url, **kwargs)

    def get_auth_header(self, method, url):
        """Generates the OAuth 1.0 Authorization header for NetSuite TBA."""
        from urllib.parse import urlparse, parse_qsl, urlunparse
        
        parsed_url = urlparse(url)
        # Reconstruct base URL without query parameters
        base_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))
        
        params = {
            'oauth_consumer_key': self.consumer_key,
            'oauth_token': self.token_id,
            'oauth_nonce': uuid.uuid4().hex,
            'oauth_timestamp': str(int(time.time())),
            'oauth_signature_method': 'HMAC-SHA256',
            'oauth_version': '1.0'
        }
        
        # Parse query parameters from the URL and add them to the params dictionary
        query_params = parse_qsl(parsed_url.query)
        for k, v in query_params:
            params[k] = v
            
        # Base string for signature
        sorted_params = sorted(params.items())
        encoded_params = urlencode(sorted_params, quote_via=quote)
        
        base_string = f"{method.upper()}&{quote(base_url, safe='')}&{quote(encoded_params, safe='')}"
        key = f"{quote(self.consumer_secret, safe='')}&{quote(self.token_secret, safe='')}"
        
        signature = base64.b64encode(
            hmac.new(key.encode(), base_string.encode(), hashlib.sha256).digest()
        ).decode()
        
        # Prepare the OAuth parameters for the header.
        # Only oauth_* parameters and realm are included in the header (exclude query params).
        header_params = {
            'oauth_consumer_key': self.consumer_key,
            'oauth_token': self.token_id,
            'oauth_nonce': params['oauth_nonce'],
            'oauth_timestamp': params['oauth_timestamp'],
            'oauth_signature_method': 'HMAC-SHA256',
            'oauth_version': '1.0',
            'oauth_signature': signature,
            'realm': self.account_id.upper().replace("-", "_")
        }
        
        auth_header = "OAuth " + ", ".join([f'{k}="{quote(v, safe="")}"' for k, v in sorted(header_params.items())])
        return auth_header

    def push_invoice(self, invoice_doc, file_log=None):
        """Pushes an ERPNext Sales Invoice to NetSuite as an invoice."""
        if not self.settings.netsuite_enabled:
            return {"status": "Skipped", "message": "NetSuite Sync Disabled"}

        payload = self.prepare_payload(invoice_doc)
        
        # Derive invoice endpoint URL from netsuite_rest_url
        url = self.base_url
        for word in ["salesOrder", "customerPayment"]:
            if url.endswith("/" + word):
                url = url[:-len(word)] + "invoice"
                break
            elif "/" + word + "?" in url:
                url = url.replace("/" + word + "?", "/invoice?")
                break
        else:
            if "/salesOrder" in url:
                url = url.replace("/salesOrder", "/invoice")
            elif "/customerPayment" in url:
                url = url.replace("/customerPayment", "/invoice")
            elif not url.endswith("/invoice"):
                url = url.rstrip('/') + '/invoice'

        headers = {
            "Authorization": self.get_auth_header("POST", url),
            "Content-Type": "application/json"
        }

        try:
            print("SENDING PAYLOAD TO NETSUITE:", json.dumps(payload, indent=2))
            response = self._request("POST", url, data=json.dumps(payload), headers=headers)
            print("NETSUITE RESPONSE STATUS:", response.status_code)
            print("NETSUITE RESPONSE BODY:", response.text)
            
            ns_id = None
            if response.status_code in [200, 201, 204]:
                if response.text and response.text.strip():
                    try:
                        res_data = response.json()
                        ns_id = res_data.get("internalId") or res_data.get("id")
                    except Exception:
                        pass
                
                if not ns_id:
                    location_header = response.headers.get("Location")
                    if location_header:
                        ns_id = location_header.rstrip("/").split("/")[-1].split("?")[0]
                
                if ns_id:
                    invoice_doc.db_set("netsuite_id", ns_id)
                    self.log_sync_attempt("Sales Invoice", invoice_doc.name, "Success", payload, response.text, None, file_log)
                    return {"status": "Success", "ns_id": ns_id}
                
                if response.status_code == 204:
                    self.log_sync_attempt("Sales Invoice", invoice_doc.name, "Success", payload, response.text, "Record created (204 No Content)", file_log)
                    return {"status": "Success", "message": "Record created (204 No Content)"}
            
            error_msg = None
            is_duplicate = False
            if response.text and response.text.strip():
                try:
                    res_data = response.json()
                    error_msg = res_data.get("error", {}).get("message") or response.text
                    for detail in res_data.get("o:errorDetails", []):
                        if "already exists" in str(detail.get("detail")).lower():
                            is_duplicate = True
                except Exception:
                    error_msg = response.text
            else:
                error_msg = f"HTTP {response.status_code}"
                
            if is_duplicate:
                recovered_id = self.recover_record_id("invoice", invoice_doc.name)
                if recovered_id:
                    invoice_doc.db_set("netsuite_id", recovered_id)
                    self.log_sync_attempt("Sales Invoice", invoice_doc.name, "Success", payload, response.text, f"Duplicate recovered ID: {recovered_id}", file_log)
                    return {"status": "Success", "ns_id": recovered_id, "message": "Recovered existing record ID"}

            self.log_sync_attempt("Sales Invoice", invoice_doc.name, "Failed", payload, response.text, error_msg, file_log)
            frappe.log_error(title=f"NetSuite Push Failed: {invoice_doc.name}", message=error_msg)
            return {"status": "Failed", "error": error_msg}
            
        except Exception as e:
            self.log_sync_attempt("Sales Invoice", invoice_doc.name, "Failed", payload, None, str(e), file_log)
            frappe.log_error(title="NetSuite Connection Error", message=frappe.get_traceback())
            return {"status": "Failed", "error": str(e)}

    def test_connection(self):
        """Tests the NetSuite integration credentials/URL connection."""
        if not self.settings.netsuite_enabled:
            return {"status": "Disabled", "message": "NetSuite Sync Disabled"}

        url = self.base_url
        if not url:
            return {"status": "Failed", "message": "NetSuite REST URL is not configured."}

        if "/salesOrder" in url:
            test_url = url.replace("/salesOrder", "/inventoryItem") + "?limit=1"
        elif "/invoice" in url:
            test_url = url.replace("/invoice", "/inventoryItem") + "?limit=1"
        else:
            test_url = url.rstrip('/') + '/inventoryItem?limit=1'

        headers = {
            "Authorization": self.get_auth_header("GET", test_url),
            "Content-Type": "application/json"
        }
        try:
            response = self._request("GET", test_url, headers=headers, timeout=10)
            if response.status_code in [200, 201]:
                return {"status": "Success", "message": "Successfully connected to NetSuite REST API."}
            else:
                try:
                    res_data = response.json()
                    error_msg = res_data.get("error", {}).get("message") or response.text
                except Exception:
                    error_msg = response.text
                return {"status": "Failed", "message": f"NetSuite returned HTTP {response.status_code}: {error_msg}"}
        except Exception as e:
            return {"status": "Failed", "message": f"Connection error: {str(e)}"}

    def get_item_internal_id(self, item_code):
        """Resolves the NetSuite internal ID for a given ERPNext item_code/barcode."""
        # 1. Check Frappe cache
        cache_key = f"ns_item_id:{item_code}"
        cached_id = frappe.cache().get_value(cache_key)
        if cached_id:
            return cached_id

        # 2. Generate candidate NetSuite itemIds
        candidates = []
        candidates.append(item_code)
        
        stripped = item_code.lstrip('0')
        if stripped:
            candidates.append(stripped)
            if len(stripped) < 5:
                candidates.append(stripped.zfill(5))
        
        if len(item_code) >= 4:
            candidates.append("1" + item_code[-4:])
        if len(item_code) >= 3:
            candidates.append("10" + item_code[-3:])
            
        candidates = list(dict.fromkeys(candidates))

        # Derive NetSuite /inventoryItem search URL
        url = self.base_url
        if "/salesOrder" in url:
            search_url = url.replace("/salesOrder", "/inventoryItem")
        elif "/invoice" in url:
            search_url = url.replace("/invoice", "/inventoryItem")
        else:
            search_url = url.rstrip('/') + '/inventoryItem'

        for cand in candidates:
            query_url = f"{search_url}?q=itemId IS \"{cand}\""
            headers = {
                "Authorization": self.get_auth_header("GET", query_url),
                "Content-Type": "application/json"
            }
            try:
                response = self._request("GET", query_url, headers=headers, timeout=10)
                if response.ok:
                    data = response.json()
                    if data.get("totalResults", 0) > 0:
                        ns_id = data.get("items")[0].get("id")
                        if ns_id:
                            # Cache mapping for 24 hours
                            frappe.cache().set_value(cache_key, ns_id, expires_in_sec=86400)
                            return ns_id
            except Exception:
                pass

        # Return original code as fallback
        return item_code

    def recover_record_id(self, record_type, external_id):
        """Attempts to recover the NetSuite internal ID of an existing record by externalId."""
        url = self.base_url
        for word in ["salesOrder", "invoice"]:
            if url.endswith("/" + word):
                url = url[:-len(word)] + record_type
                break
            elif "/" + word + "?" in url:
                url = url.replace("/" + word + "?", f"/{record_type}?")
                break
        else:
            url = url.rstrip('/') + '/' + record_type

        url = url + f'?q=externalId IS "{external_id}"'
        headers = {
            "Authorization": self.get_auth_header("GET", url),
            "Content-Type": "application/json"
        }
        try:
            response = self._request("GET", url, headers=headers, timeout=10)
            if response.ok:
                data = response.json()
                if data.get("totalResults", 0) > 0:
                    ns_id = data.get("items")[0].get("id")
                    return ns_id
        except Exception as e:
            frappe.log_error(title=f"NetSuite ID Recovery Failed: {record_type} ({external_id})", message=str(e))
        return None

    def log_sync_attempt(self, doc_type, doc_name, status, payload, response_text, error_message, file_log=None):
        """Creates a standalone NetSuite Sync Log document for auditing."""
        try:
            from frappe.utils import now_datetime
            sync_log = frappe.new_doc("NetSuite Sync Log")
            sync_log.document_type = doc_type
            sync_log.document_name = doc_name
            sync_log.status = status
            sync_log.sync_time = now_datetime()
            sync_log.request_payload = json.dumps(payload, indent=2) if payload else ""
            sync_log.response_data = response_text or ""
            sync_log.error_message = error_message or ""
            sync_log.file_log = file_log
            
            # Extract netsuite_id if success
            if status == "Success":
                sync_log.netsuite_id = frappe.db.get_value(doc_type, doc_name, "netsuite_id")
                
            sync_log.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(title="Failed to log NetSuite sync attempt", message=frappe.get_traceback())

    def prepare_payload(self, doc):
        """Maps ERPNext Invoice fields to NetSuite Sales Order/Invoice format."""
        # Retrieve NetSuite Location ID from Shop Mapping
        ns_location_id = None
        if doc.teraoka_shop_code:
            ns_location_id = frappe.db.get_value("Teraoka Shop Mapping Details", 
                {"shop_code": doc.teraoka_shop_code}, "netsuite_location_id")

        # Resolve cost center from invoice header or first item
        cost_center = getattr(doc, "cost_center", None)
        if not cost_center and getattr(doc, "items", None):
            cost_center = doc.items[0].cost_center

        # Map ERPNext Cost Center to NetSuite Department ID
        department_map = {
            "Main - AT": "3"
        }
        ns_dept_id = department_map.get(cost_center, "3")

        items = []
        for item in doc.items:
            if item.item_code == "0" or str(item.item_code).strip() == "0":
                continue
            ns_item_id = self.get_item_internal_id(item.item_code)
            if ns_item_id == "0" or str(ns_item_id).strip() == "0":
                continue
            items.append({
                "item": {"id": ns_item_id},
                "quantity": item.qty,
                "rate": item.rate,
                "taxCode": {"id": "2824"},
                "location": {"id": ns_location_id} if ns_location_id else None,
                "department": {"id": str(ns_dept_id)},
                "class": {"id": str(ns_dept_id)}
            })
            
        # Determine NetSuite Customer Internal ID
        ns_customer_id = self.settings.netsuite_customer_id
        if not ns_customer_id:
            ns_customer_id = doc.customer
        elif str(ns_customer_id).isdigit():
            ns_customer_id = int(ns_customer_id)

        # Map Mode of Payment
        # NetSuite customlist_list_made_of_payment IDs: 5 (Cash Payment), 6 (Credit Card)
        ns_payment_mode_id = "5" # Default to Cash Payment
        erp_payment_modes = [p.mode_of_payment for p in getattr(doc, "payments", []) if getattr(p, "amount", 0) > 0]
        if erp_payment_modes:
            mode = str(erp_payment_modes[0]).lower()
            if any(x in mode for x in ["card", "credit", "visa", "master", "amex"]):
                ns_payment_mode_id = "6" # Credit Card
            elif "cash" in mode:
                ns_payment_mode_id = "5" # Cash Payment

        # Determine NetSuite Currency reference
        currency_map = {
            "JPY": "1", # Map to 1 in sandbox since the customer record only supports currency 1 (INR)
            "INR": "1",
            "USD": "1"
        }
        ns_currency_id = currency_map.get(doc.currency, "1")

        payload = {
            "entity": {"id": ns_customer_id}, # NetSuite Customer Internal ID
            "trandate": str(doc.posting_date),
            "externalId": doc.name + "_INV",
            "location": {"id": ns_location_id} if ns_location_id else None,
            "memo": f"Teraoka POS Sync | Shop: {doc.teraoka_shop_code or 'N/A'}",
            "item": {"items": items},
            "currency": {"id": ns_currency_id},
            "custbody_mode_of_order": {"id": "8"}, # POS Order Mode
            "custbody_mode_of_payment": {"id": ns_payment_mode_id},
            "department": {"id": str(ns_dept_id)},
            "class": {"id": str(ns_dept_id)},
            "custbody_dispatch_date": str(doc.posting_date)
        }
        
        return payload

    def push_payment(self, payment_doc, netsuite_invoice_id, file_log=None):
        """Pushes an ERPNext Payment Entry to NetSuite as a customerPayment."""
        if not self.settings.netsuite_enabled:
            return {"status": "Skipped", "message": "NetSuite Sync Disabled"}

        # Derive customerPayment endpoint URL from netsuite_rest_url
        url = self.base_url
        for word in ["salesOrder", "invoice"]:
            if url.endswith("/" + word):
                url = url[:-len(word)] + "customerPayment"
                break
            elif "/" + word + "?" in url:
                url = url.replace("/" + word + "?", "/customerPayment?")
                break
        else:
            if "/salesOrder" in url:
                url = url.replace("/salesOrder", "/customerPayment")
            elif "/invoice" in url:
                url = url.replace("/invoice", "/customerPayment")
            else:
                url = url.rstrip('/') + '/customerPayment'

        # Fetch NetSuite Location ID based on mapping (if available)
        ns_location_id = None
        sales_invoice_name = None
        for ref in payment_doc.references:
            if ref.reference_doctype == "Sales Invoice":
                sales_invoice_name = ref.reference_name
                break

        if sales_invoice_name:
            shop_code = frappe.db.get_value("Sales Invoice", sales_invoice_name, "teraoka_shop_code")
            if shop_code:
                ns_location_id = frappe.db.get_value("Teraoka Shop Mapping Details", 
                    {"shop_code": shop_code}, "netsuite_location_id")

        # Determine NetSuite Customer Internal ID
        ns_customer_id = self.settings.netsuite_customer_id
        if not ns_customer_id:
            ns_customer_id = payment_doc.party
        elif str(ns_customer_id).isdigit():
            ns_customer_id = int(ns_customer_id)

        # Prepare payload applying payment to the NetSuite invoice ID
        payload = {
            "customer": {"id": ns_customer_id}, # NetSuite Customer Internal ID
            "payment": float(payment_doc.paid_amount),
            "trandate": str(payment_doc.posting_date),
            "externalId": payment_doc.name,
            "memo": f"Teraoka POS Sync Payment | Invoice: {sales_invoice_name or 'N/A'}",
            "apply": {
                "items": [
                    {
                        "doc": {"id": netsuite_invoice_id},
                        "apply": True,
                        "amount": float(payment_doc.paid_amount)
                    }
                ]
            }
        }
        if ns_location_id:
            payload["location"] = {"id": ns_location_id}

        headers = {
            "Authorization": self.get_auth_header("POST", url),
            "Content-Type": "application/json"
        }

        try:
            response = self._request("POST", url, data=json.dumps(payload), headers=headers)
            
            ns_id = None
            if response.status_code in [200, 201, 204]:
                if response.text and response.text.strip():
                    try:
                        res_data = response.json()
                        ns_id = res_data.get("internalId") or res_data.get("id")
                    except Exception:
                        pass
                
                if not ns_id:
                    location_header = response.headers.get("Location")
                    if location_header:
                        ns_id = location_header.rstrip("/").split("/")[-1].split("?")[0]
                
                if ns_id:
                    payment_doc.db_set("netsuite_id", ns_id)
                    self.log_sync_attempt("Payment Entry", payment_doc.name, "Success", payload, response.text, None, file_log)
                    return {"status": "Success", "ns_id": ns_id}
                
                if response.status_code == 204:
                    self.log_sync_attempt("Payment Entry", payment_doc.name, "Success", payload, response.text, "Payment created (204 No Content)", file_log)
                    return {"status": "Success", "message": "Payment created (204 No Content)"}
            
            error_msg = None
            is_duplicate = False
            if response.text and response.text.strip():
                try:
                    res_data = response.json()
                    error_msg = res_data.get("error", {}).get("message") or response.text
                    for detail in res_data.get("o:errorDetails", []):
                        if "already exists" in str(detail.get("detail")).lower():
                            is_duplicate = True
                except Exception:
                    error_msg = response.text
            else:
                error_msg = f"HTTP {response.status_code}"
                
            if is_duplicate:
                recovered_id = self.recover_record_id("customerPayment", payment_doc.name)
                if recovered_id:
                    payment_doc.db_set("netsuite_id", recovered_id)
                    self.log_sync_attempt("Payment Entry", payment_doc.name, "Success", payload, response.text, f"Duplicate recovered ID: {recovered_id}", file_log)
                    return {"status": "Success", "ns_id": recovered_id, "message": "Recovered existing payment ID"}

            self.log_sync_attempt("Payment Entry", payment_doc.name, "Failed", payload, response.text, error_msg, file_log)
            frappe.log_error(title=f"NetSuite Payment Push Failed: {payment_doc.name}", message=error_msg)
            return {"status": "Failed", "error": error_msg}
            
        except Exception as e:
            self.log_sync_attempt("Payment Entry", payment_doc.name, "Failed", payload, None, str(e), file_log)
            frappe.log_error(title="NetSuite Payment Connection Error", message=frappe.get_traceback())
            return {"status": "Failed", "error": str(e)}

def push_to_erp(invoice_name, file_log=None):
    """Entry point for NetSuite synchronization."""
    settings = frappe.get_single("Teraoka Settings")
    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    
    connector = NetSuiteConnector(settings)
    return connector.push_invoice(invoice, file_log=file_log)

def push_payment_to_erp(payment_name, netsuite_invoice_id, file_log=None):
    """Entry point for NetSuite Customer Payment synchronization."""
    settings = frappe.get_single("Teraoka Settings")
    payment_doc = frappe.get_doc("Payment Entry", payment_name)
    
    connector = NetSuiteConnector(settings)
    return connector.push_payment(payment_doc, netsuite_invoice_id, file_log=file_log)

def retry_failed_netsuite_syncs():
    """
    Background task to retry synchronizing orphaned invoices and payment entries.
    Scans for submitted records with missing NetSuite IDs from the last 48 hours.
    """
    from frappe.utils import add_days, nowdate
    
    settings = frappe.get_single("Teraoka Settings")
    if not settings.netsuite_enabled:
        return
        
    threshold_date = add_days(nowdate(), -2)
    
    # 1. Retry Invoices
    orphaned_invoices = frappe.get_all("Sales Invoice", filters={
        "docstatus": 1,
        "netsuite_id": ["in", ["", None]],
        "posting_date": [">=", threshold_date],
        "company": settings.company
    }, fields=["name"])
    
    for inv in orphaned_invoices:
        try:
            push_to_erp(inv.name)
        except Exception:
            continue
            
    # 2. Retry Payment Entries
    orphaned_payments = frappe.get_all("Payment Entry", filters={
        "docstatus": 1,
        "netsuite_id": ["in", ["", None]],
        "posting_date": [">=", threshold_date],
        "company": settings.company
    }, fields=["name"])
    
    for pe_meta in orphaned_payments:
        try:
            pe = frappe.get_doc("Payment Entry", pe_meta.name)
            invoice_name = None
            for ref in pe.references:
                if ref.reference_doctype == "Sales Invoice":
                    invoice_name = ref.reference_name
                    break
                    
            if invoice_name:
                netsuite_invoice_id = frappe.db.get_value("Sales Invoice", invoice_name, "netsuite_id")
                if netsuite_invoice_id:
                    push_payment_to_erp(pe.name, netsuite_invoice_id)
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

@frappe.whitelist()
def enqueue_sync_log(log_name):
    """Enqueues the sync process as a background job to prevent Gunicorn timeouts."""
    current_status = frappe.db.get_value("Teraoka File Log", log_name, "status")
    if current_status in ["Syncing", "Failed", "Partial Success"]:
        frappe.db.set_value("Teraoka File Log", log_name, "status", "Pending Sync", update_modified=True)
        frappe.db.commit()
        
    frappe.enqueue(
        "teraoka_integration.teraoka_integration.services.netsuite.sync_log_to_netsuite",
        queue="default",
        log_name=log_name,
        timeout=1500
    )
    return "Enqueued"

def sync_log_to_netsuite(log_name):
    """
    Background Job to sync a specific File Log to NetSuite and send Google Chat webhook.
    """
    # Atomic check and update status to prevent race conditions during concurrent runs
    current_status = frappe.db.get_value("Teraoka File Log", log_name, "status")
    if current_status not in ["Pending Sync", "Failed", "Partial Success"]:
        return

    frappe.db.set_value("Teraoka File Log", log_name, "status", "Syncing", update_modified=True)
    frappe.db.commit()

    log = frappe.get_doc("Teraoka File Log", log_name)
    settings = frappe.get_single("Teraoka Settings")
    
    invoices = frappe.get_all("Sales Invoice", filters={
        "docstatus": 1,
        "teraoka_shop_code": log.shop_code,
        "posting_date": log.file_date,
        "company": settings.company
    }, fields=["name", "remarks", "netsuite_id"])
    
    success_count = 0
    error_count = 0
    errors = []
    
    # Helper to parse transaction ID from Sales Invoice remarks
    def get_transaction_id(si_doc_name, remarks):
        if not remarks:
            return "Unknown"
        import re
        match = re.search(r"Transaction ID:\s*([^\n]+)", remarks)
        return match.group(1).strip() if match else "Unknown"

    def update_or_append_detail(log_doc, txn_id, doc_type, doc_name, status, error_message):
        found = False
        for row in log_doc.transaction_details:
            if row.doc_type == doc_type and row.doc_name == doc_name:
                row.status = status
                row.error_message = error_message
                found = True
                break
        if not found:
            log_doc.append("transaction_details", {
                "transaction_id": txn_id,
                "doc_type": doc_type,
                "doc_name": doc_name,
                "status": status,
                "error_message": error_message
            })

    for inv in invoices:
        txn_id = get_transaction_id(inv.name, inv.remarks)
        netsuite_invoice_id = inv.netsuite_id
        invoice_pushed = False
        res = {"status": "Success", "ns_id": netsuite_invoice_id}
        
        if not netsuite_invoice_id:
            res = push_to_erp(inv.name, file_log=log_name)
            invoice_pushed = True
            
            # Log Sales Invoice sync detail
            update_or_append_detail(
                log,
                txn_id,
                "Sales Invoice",
                inv.name,
                "Success" if res.get("status") == "Success" else "Failed",
                str(res.get("error") or res.get("message") or "") if res.get("status") != "Success" else ""
            )
            
            if res.get("status") == "Success":
                netsuite_invoice_id = res.get("ns_id")
                success_count += 1
            else:
                error_count += 1
                errors.append(str(res.get("error") or res.get("message") or "Unknown Error"))
        else:
            success_count += 1
            
        if netsuite_invoice_id:
            # Push corresponding Payment Entry if one exists
            pe_name = frappe.db.get_value(
                "Payment Entry Reference",
                {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": inv.name,
                    "docstatus": 1
                },
                "parent"
            )
            if pe_name:
                pe_ns_id = frappe.db.get_value("Payment Entry", pe_name, "netsuite_id")
                if not pe_ns_id:
                    pe_res = push_payment_to_erp(pe_name, netsuite_invoice_id, file_log=log_name)
                    
                    # Log Payment Entry sync detail
                    update_or_append_detail(
                        log,
                        txn_id,
                        "Payment Entry",
                        pe_name,
                        "Success" if pe_res.get("status") == "Success" else "Failed",
                        str(pe_res.get("error") or pe_res.get("message") or "") if pe_res.get("status") != "Success" else ""
                    )

                    if pe_res.get("status") != "Success":
                        errors.append(f"Payment Entry {pe_name} Sync Failed: {pe_res.get('error') or pe_res.get('message') or 'Unknown Error'}")

    # Count total invoices and synced invoices
    total_invs = len(invoices)
    synced_invs = sum(1 for inv in invoices if frappe.db.get_value("Sales Invoice", inv.name, "netsuite_id"))
    
    # Count total payment entries and synced payment entries
    total_pes = 0
    synced_pes = 0
    
    for inv in invoices:
        pe_name = frappe.db.get_value(
            "Payment Entry Reference",
            {
                "reference_doctype": "Sales Invoice",
                "reference_name": inv.name,
                "docstatus": 1
            },
            "parent"
        )
        if pe_name:
            total_pes += 1
            if frappe.db.get_value("Payment Entry", pe_name, "netsuite_id"):
                synced_pes += 1

    # Update File Log status based on DB state
    if not invoices:
        if current_status in ["Failed", "Partial Success"]:
            log.status = current_status
        else:
            log.status = "Success"
    elif synced_invs == total_invs and synced_pes == total_pes:
        if getattr(log, "error_count", 0) > 0:
            log.status = "Partial Success"
        else:
            log.status = "Success"
    elif synced_invs > 0:
        log.status = "Partial Success"
    else:
        log.status = "Failed"
        
    if errors:
        log.logs = (log.logs or "") + "\n" + "\n".join(errors)
        
    # Send Google Chat Notification on failure
    chat_err = ""
    if invoices and settings.google_chat_webhook_url and log.status in ("Failed", "Partial Success"):
        _, chat_err = send_google_chat_notification(
            log,
            settings.google_chat_webhook_url,
            success_count=success_count,
            error_count=error_count,
            is_netsuite_sync=True
        )
        
    log.google_chat_error = chat_err
    log.save(ignore_permissions=True)
    frappe.db.commit()
    
    # Archive file if enabled
    if log.status in ("Success", "Partial Success") and settings.archive_processed_files:
        try:
            from .ftp import archive_file, TeraokaConnector
            with TeraokaConnector(settings) as tconn:
                archive_file(settings, log.filename, conn_obj=tconn)
        except Exception as e:
            frappe.logger("teraoka").error(f"Failed to archive file {log.filename}: {e}")

# Google Chat functions relocated to google_chat.py
