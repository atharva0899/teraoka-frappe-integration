import frappe
import os
from frappe.utils import now_datetime, getdate

def wipe_integration_data():
    print("Starting Data Wipe...")
    frappe.db.sql("DELETE FROM `tabTeraoka File Log Detail`")
    frappe.db.sql("DELETE FROM `tabTeraoka File Log`")
    frappe.db.sql("DELETE FROM `tabSales Invoice Item`")
    frappe.db.sql("DELETE FROM `tabSales Invoice`")
    frappe.db.sql("DELETE FROM `tabPayment Entry Reference`")
    frappe.db.sql("DELETE FROM `tabPayment Entry`")
    frappe.db.sql("DELETE FROM `tabError Log` WHERE method LIKE '%Teraoka%' OR method LIKE '%NetSuite%' OR error LIKE '%Teraoka%' OR error LIKE '%NetSuite%'")
    frappe.db.commit()
    print("Data Wipe Complete.")

def execute():
    from teraoka_integration.teraoka_integration.services.parser import parse_raw_lines
    from teraoka_integration.teraoka_integration.services.splitter import group_transactions
    from teraoka_integration.teraoka_integration.services.mapper import map_transactions
    from teraoka_integration.teraoka_integration.services.invoice import create_sales_invoice_from_txn
    from teraoka_integration.teraoka_integration.services.process import attach_file_to_log

    # 1. Wipe data
    wipe_integration_data()

    # 2. Setup the test file log doc
    filename = "LGYOUMU.001"
    local_path = f"/opt/bench/frappe-bench/sites/atharvaj-dev/private/files/{filename}"
    
    print(f"\nStep 1: Creating Teraoka File Log Doc for '{filename}'...")
    log = frappe.new_doc("Teraoka File Log")
    log.filename = filename
    log.status = "Pending"
    log.insert()
    frappe.db.commit()
    print(f"  Created Log Doc: {log.name}")

    # 3. Attach file
    print("Step 2: Attaching local file to Log Doc...")
    attach_file_to_log(filename, local_path, log)
    log.save()
    frappe.db.commit()
    print(f"  Attached File URL: {log.attached_file}")

    # 4. Parse & Map
    print("Step 3: Parsing and mapping transactions...")
    raw_lines = parse_raw_lines(local_path)
    grouped_txns = group_transactions(raw_lines)
    mapped_data = map_transactions(grouped_txns)
    print(f"  Total mapped: {len(mapped_data)}")

    # 5. Populate stats on the main log
    print("Step 4: Initializing stats on File Log Doc...")
    log.status = "Pending"
    log.success_count = 0
    log.error_count = 0
    log.total_records = len(mapped_data)
    log.total_quantity = sum(sum(item.get('qty', 0) for item in txn.get('items', [])) for txn in mapped_data)
    log.total_amount = sum(sum(item.get('amount', 0) for item in txn.get('items', [])) for txn in mapped_data)
    log.shop_code = "001"
    log.file_date = mapped_data[0].get("date") if mapped_data else getdate()
    log.processed_on = now_datetime()
    log.save()
    frappe.db.commit()
    
    print(f"  File Log Status initialized. Total Amount = {log.total_amount}, Records = {log.total_records}")

    # 6. Process each transaction synchronously and update the log & details
    print("Step 5: Processing transactions synchronously (updating log and inserting details)...")
    settings = frappe.get_single("Teraoka Settings")
    
    for txn in mapped_data:
        txn_id = txn.get("transaction_id")
        inv_result = create_sales_invoice_from_txn(txn, settings)
        final_status = inv_result.get("status")
        error_msg = inv_result.get("error")
        
        # Create Log Detail Row
        detail = frappe.new_doc("Teraoka File Log Detail")
        detail.parent = log.name
        detail.parenttype = "Teraoka File Log"
        detail.parentfield = "transaction_details"
        detail.transaction_id = txn_id or "Unknown"
        detail.doc_type = "Sales Invoice"
        detail.doc_name = inv_result.get("invoice") or ""
        detail.status = final_status
        detail.error_message = error_msg or ""
        detail.insert(ignore_permissions=True)

        if final_status in ("Success", "Skipped"):
            frappe.db.sql("""
                UPDATE `tabTeraoka File Log` 
                SET success_count = ifnull(success_count, 0) + 1 
                WHERE name = %s
            """, (log.name,))
        else:
            error_log = f"\n[{final_status.upper()}] TXN {txn_id}: {error_msg}"
            frappe.db.sql("""
                UPDATE `tabTeraoka File Log` 
                SET 
                    error_count = ifnull(error_count, 0) + 1,
                    logs = CONCAT(ifnull(logs, ''), %s)
                WHERE name = %s
            """, (error_log, log.name))
        
        frappe.db.commit()
        print(f"    TXN {txn_id} -> Result: {final_status}")

    # 7. Finalize status
    log.reload()
    final_log_status = "Pending Sync"
    if log.success_count == 0 and log.total_records > 0:
        final_log_status = "Failed"
    
    log.status = final_log_status
    log.save()
    frappe.db.commit()
    print(f"  Final File Log Status set to: {log.status}")

    # 8. Fetch the finalized log and print everything to verify
    print("\n=== STEP 6: VERIFYING TERAOKA FILE LOG FROM DB ===")
    final_log = frappe.get_doc("Teraoka File Log", log.name)
    print(f"Log Name: {final_log.name}")
    print(f"  Filename: {final_log.filename}")
    print(f"  Status: {final_log.status}")
    print(f"  Shop Code: {final_log.shop_code} | Date: {final_log.file_date}")
    print(f"  Total Records: {final_log.total_records}")
    print(f"  Total Amount: {final_log.total_amount} | Qty: {final_log.total_quantity}")
    print(f"  Success Count: {final_log.success_count} | Error Count: {final_log.error_count}")
    print(f"  Attached File URL: {final_log.attached_file}")
    
    print("  Transaction Details Child Rows:")
    for row in final_log.transaction_details:
        print(f"    - TXN ID: {row.transaction_id} | Doc: {row.doc_name} | Status: {row.status} | Err: {row.error_message or 'None'}")

def run_full_test():
    settings = frappe.get_single("Teraoka Settings")
    for row in settings.shop_mappings:
        if not row.company:
            row.company = "Ambibuzz Tech"
        if not row.warehouse:
            row.warehouse = "Stores - AT"
        if not row.cost_center:
            row.cost_center = "Main - AT"
    original_enabled = settings.netsuite_enabled
    
    try:
        # Enable NetSuite sync temporarily
        settings.netsuite_enabled = 1
        settings.save(ignore_permissions=True)
        frappe.db.commit()
        print("Temporarily enabled NetSuite Sync in settings.")
        
        # 1. Run POS import test
        print("Running POS Import...")
        execute()
        
        # 2. Get the created log
        log_name = frappe.db.get_value("Teraoka File Log", {"status": "Pending Sync"}, "name")
        if not log_name:
            print("Error: No Pending Sync File Log found after POS import.")
            return
            
        print(f"Found Pending Sync File Log: {log_name}")
        
        # 3. Trigger NetSuite sync
        print(f"Triggering sync to NetSuite for {log_name}...")
        from teraoka_integration.teraoka_integration.services.netsuite import sync_log_to_netsuite
        sync_log_to_netsuite(log_name)
        
        # 4. Fetch the log and print status and errors
        log = frappe.get_doc("Teraoka File Log", log_name)
        print("\n=== Test Execution Results ===")
        print(f"Log Status: {log.status}")
        print(f"Success Count: {log.success_count}")
        print(f"Error Count: {log.error_count}")
        print(f"Google Chat Error: {log.google_chat_error or 'None'}")
        
        print("\nChild Transaction Details:")
        for row in log.transaction_details:
            print(f"  - TXN: {row.transaction_id} | Type: {row.doc_type} | Name: {row.doc_name} | Status: {row.status} | Err: {row.error_message or 'None'}")
            
    finally:
        # Restore settings
        settings = frappe.get_single("Teraoka Settings")
        settings.netsuite_enabled = original_enabled
        settings.save(ignore_permissions=True)
        frappe.db.commit()
        print("\nRestored NetSuite Sync setting to:", original_enabled)


def query_sync_logs():
    logs = frappe.db.get_all('NetSuite Sync Log', fields=['document_type', 'document_name', 'status', 'error_message'], order_by='creation desc', limit=15)
    print("=== LATEST NETSUITE SYNC LOGS ===")
    for log in logs:
        print(f"DocType: {log.document_type} | DocName: {log.document_name} | Status: {log.status} | Err: {log.error_message or 'None'}")


def debug_log(name):
    log = frappe.get_doc("Teraoka File Log", name)
    print("STATUS:", log.status)
    print("SUCCESS COUNT:", log.success_count)
    print("ERROR COUNT:", log.error_count)
    print("LOGS:", log.logs)
    print("GOOGLE CHAT ERROR:", log.google_chat_error)
    print("DETAILS:")
    for row in log.transaction_details:
        print(f"  TXN: {row.transaction_id} | Doc: {row.doc_name} | DocType: {row.doc_type} | Status: {row.status} | Err: {row.error_message}")


def list_remote_files():
    from teraoka_integration.teraoka_integration.services.ftp import list_files, TeraokaConnector
    settings = frappe.get_single("Teraoka Settings")
    print("Connecting to:", settings.host)
    with TeraokaConnector(settings) as tconn:
        files = list_files(settings, conn_obj=tconn)
        print("Files on remote SFTP server:")
        for f in files:
            print("-", f)


def run_teraoka_test_data():
    from teraoka_integration.teraoka_integration.services.ftp import download_file, TeraokaConnector
    from teraoka_integration.teraoka_integration.services.process import attach_file_to_log
    from teraoka_integration.teraoka_integration.services.parser import parse_csv, parse_raw_lines
    from teraoka_integration.teraoka_integration.services.splitter import group_transactions
    from teraoka_integration.teraoka_integration.services.mapper import map_transactions
    from teraoka_integration.teraoka_integration.services.queue_manager import process_single_transaction
    from teraoka_integration.teraoka_integration.services.invoice import create_sales_invoices
    import os
    import re
    from frappe.utils import now_datetime, getdate

    filename = "teraoka_test_data.csv"
    
    # 1. Wipe existing log for this file to ensure clean run
    existing_log = frappe.db.get_value("Teraoka File Log", {"filename": filename}, "name")
    if existing_log:
        print(f"Deleting existing log: {existing_log}")
        # Wipe associated invoices and payments if we want a fresh run
        details = frappe.db.get_all("Teraoka File Log Detail", filters={"parent": existing_log}, fields=["doc_type", "doc_name"])
        for d in details:
            if d.doc_name:
                print(f"Deleting created doc: {d.doc_type} {d.doc_name}")
                try:
                    doc = frappe.get_doc(d.doc_type, d.doc_name)
                    if doc.docstatus == 1:
                        doc.cancel()
                    doc.delete()
                except Exception as e:
                    print(f"Error deleting doc: {e}")
        frappe.db.sql("DELETE FROM `tabTeraoka File Log Detail` WHERE parent = %s", (existing_log,))
        frappe.db.sql("DELETE FROM `tabTeraoka File Log` WHERE name = %s", (existing_log,))
        frappe.db.commit()
        
    # 2. Create new log doc
    print(f"Creating new file log for {filename}...")
    log = frappe.new_doc("Teraoka File Log")
    log.filename = filename
    log.status = "Pending"
    log.insert()
    frappe.db.commit()
    
    # 3. Download the file from SFTP
    settings = frappe.get_single("Teraoka Settings")
    local_path = os.path.join(frappe.get_site_path("private", "files"), filename)
    print(f"Downloading remote file {filename} to {local_path}...")
    with TeraokaConnector(settings) as tconn:
        download_file(settings, filename, local_path, conn_obj=tconn)
        
    # 4. Attach file to log
    print("Attaching file to log...")
    attach_file_to_log(filename, local_path, log)
    log.save()
    frappe.db.commit()
    
    # 5. Process the file synchronously (handling transactional vs legacy)
    print("Processing file contents synchronously...")
    try:
        result_data = parse_csv(local_path)
        data = result_data.get("items", {})
        summary = result_data.get("summary", {})
        
        raw_lines = parse_raw_lines(local_path)
        grouped_txns = group_transactions(raw_lines)
        mapped_data = map_transactions(grouped_txns)
        
        shop_code = filename.split("_")[0] if "_" in filename else "Default"
        if "GYOUMU" in filename.upper(): 
            shop_code = filename[0]
        
        if mapped_data and len(mapped_data) > 0:
            shop_code = mapped_data[0].get("store_code", shop_code)
        
        posting_date = summary.get("posting_date")
        if not posting_date:
            date_match = re.search(r"(\d{8})", filename)
            if date_match:
                date_str = date_match.group(1)
                if date_str.startswith('20'):
                    posting_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

        if mapped_data:
            print(f"Detected transactional format. Total transactions: {len(mapped_data)}")
            log.status = "Pending"
            log.success_count = 0
            log.error_count = 0
            log.total_records = len(mapped_data)
            log.total_quantity = sum(sum(item.get('qty', 0) for item in txn.get('items', [])) for txn in mapped_data)
            log.total_amount = sum(sum(item.get('amount', 0) for item in txn.get('items', [])) for txn in mapped_data)
            if len(mapped_data) > 0 and mapped_data[0].get("date"):
                posting_date = mapped_data[0].get("date")
            log.shop_code = shop_code
            log.file_date = posting_date or getdate()
            log.processed_on = now_datetime()
            log.save()
            frappe.db.commit()
            
            # Run transactions synchronously
            for idx, txn in enumerate(mapped_data):
                print(f"Processing transaction {idx+1}/{len(mapped_data)}: {txn.get('transaction_id')}")
                process_single_transaction(txn, log.name)
        else:
            print("Detected legacy/aggregated format.")
            result = create_sales_invoices(data, settings, shop_code, posting_date)
            invoices = result.get("invoices", [])
            log.status = "Pending Sync"
            if not invoices and result.get("error_count"):
                log.status = "Failed"
                
            log.success_count = result.get("success_count", 0)
            log.error_count = result.get("error_count", 0)
            log.total_records = len(invoices) + log.error_count
            log.total_quantity = summary.get("total_qty", 0.0)
            log.total_amount = summary.get("total_amount", 0.0)
            log.shop_code = shop_code
            log.file_date = posting_date or getdate()
            log.processed_on = now_datetime()
            log.save()
            frappe.db.commit()
            
            print(f"Created invoices: {invoices}")
            
    except Exception as e:
        import traceback
        log.status = "Failed"
        log.logs = traceback.format_exc()
        log.processed_on = now_datetime()
        log.save()
        frappe.db.commit()
        print(f"Processing failed: {e}")
        traceback.print_exc()

    # 6. Fetch and print final status
    log.reload()
    print("=== Processing Complete ===")
    print(f"Final Status: {log.status}")
    print(f"Total Quantity: {log.total_quantity}")
    print(f"Total Sale Value (Amount): {log.total_amount}")
    print(f"Success Count: {log.success_count}")
    print(f"Error Count: {log.error_count}")
    print(f"Google Chat Error: {log.google_chat_error or 'None'}")
    
    print("\nFile Log Detail Rows:")
    details = frappe.db.get_all("Teraoka File Log Detail", filters={"parent": log.name}, fields=["transaction_id", "doc_type", "doc_name", "status", "error_message"])
    for d in details:
        print(f"  - TXN: {d.transaction_id} | Type: {d.doc_type} | Name: {d.doc_name} | Status: {d.status} | Err: {d.error_message or 'None'}")


def sync_test_log_to_netsuite():
    from teraoka_integration.teraoka_integration.services.netsuite import sync_log_to_netsuite
    filename = "teraoka_test_data.csv"
    log_name = frappe.db.get_value("Teraoka File Log", {"filename": filename}, "name")
    if not log_name:
        print(f"Error: No File Log found for filename: {filename}")
        return
        
    print(f"Found File Log: {log_name}. Resetting status to 'Pending Sync' to allow sync...")
    # Change status back to Pending Sync if it was Failed/Success/etc.
    frappe.db.set_value("Teraoka File Log", log_name, "status", "Pending Sync", update_modified=True)
    frappe.db.commit()
    
    print(f"Running NetSuite sync for {log_name}...")
    sync_log_to_netsuite(log_name)
    
    log = frappe.get_doc("Teraoka File Log", log_name)
    print("=== Sync Complete ===")
    print(f"File Log Status: {log.status}")
    print(f"File Log Success Count: {log.success_count}")
    print(f"File Log Error Count: {log.error_count}")
    
    print("\nUpdated Transaction Details:")
    for row in log.transaction_details:
        print(f"  - TXN: {row.transaction_id} | Type: {row.doc_type} | Name: {row.doc_name} | Status: {row.status} | Err: {row.error_message or 'None'}")


