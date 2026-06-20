import frappe
from .netsuite import push_to_erp
from .invoice import create_sales_invoice_from_txn

def enqueue_transactions(mapped_data, log_name=None):
    """
    Takes the mapped transactions and queues them in batches of 50 for ERP processing.
    """
    chunk_size = 50
    for i in range(0, len(mapped_data), chunk_size):
        chunk = mapped_data[i:i + chunk_size]
        frappe.enqueue(
            "teraoka_integration.teraoka_integration.services.queue_manager.process_transaction_batch",
            queue='default',
            transactions_batch=chunk,
            log_name=log_name,
            timeout=600
        )

def process_transaction_batch(transactions_batch, log_name=None):
    """
    Background job to process a chunk/batch of transactions synchronously inside the worker thread.
    """
    for txn in transactions_batch:
        try:
            process_single_transaction(txn, log_name)
        except Exception as e:
            frappe.log_error(title=f"Failed to process transaction in batch {log_name}", message=frappe.get_traceback())

def process_single_transaction(transaction_data, log_name=None):
    """
    Background job to process a single transaction:
    1. Create Frappe Sales Invoice
    """
    settings = frappe.get_single("Teraoka Settings")
    
    # Step 1: Create Frappe Sales Invoice
    inv_result = create_sales_invoice_from_txn(transaction_data, settings)
    final_status = inv_result.get("status")
    error_msg = inv_result.get("error")
    
    # Step 2: Update tracking metrics on File Log safely
    if log_name:
        try:
            # Create a structured log detail row for the transaction
            detail = frappe.new_doc("Teraoka File Log Detail")
            detail.parent = log_name
            detail.parenttype = "Teraoka File Log"
            detail.parentfield = "transaction_details"
            detail.transaction_id = transaction_data.get("transaction_id") or "Unknown"
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
                """, (log_name,))
            else:
                txn_id = transaction_data.get('transaction_id')
                error_log = f"\n[{final_status.upper()}] TXN {txn_id}: {error_msg}"
                
                frappe.db.sql("""
                    UPDATE `tabTeraoka File Log` 
                    SET 
                        error_count = ifnull(error_count, 0) + 1,
                        logs = CONCAT(ifnull(logs, ''), %s)
                    WHERE name = %s
                """, (error_log, log_name))
            
            # Step 3: Finalize overarching status if all records are processed
            frappe.db.commit()
            
            log_meta = frappe.db.get_value("Teraoka File Log", log_name, ["success_count", "error_count", "total_records"], as_dict=1)
            if log_meta and (log_meta.success_count + log_meta.error_count >= log_meta.total_records):
                final_log_status = "Pending Sync"
                if log_meta.success_count == 0 and log_meta.total_records > 0:
                    final_log_status = "Failed"
                
                frappe.db.set_value("Teraoka File Log", log_name, "status", final_log_status, update_modified=True)
                frappe.db.commit()
                
                if final_log_status == "Failed" and settings.google_chat_webhook_url:
                    try:
                        log_doc = frappe.get_doc("Teraoka File Log", log_name)
                        from teraoka_integration.teraoka_integration.services.google_chat import send_google_chat_notification
                        _, chat_err = send_google_chat_notification(
                            log_doc,
                            settings.google_chat_webhook_url,
                            is_netsuite_sync=False
                        )
                        if chat_err:
                            frappe.db.set_value("Teraoka File Log", log_name, "google_chat_error", chat_err, update_modified=True)
                            frappe.db.commit()
                    except Exception as e:
                        frappe.log_error(title="Google Chat POS failure alert error", message=frappe.get_traceback())
                
        except Exception as e:
            frappe.log_error(title=f"Error updating Teraoka File Log {log_name}", message=frappe.get_traceback())
