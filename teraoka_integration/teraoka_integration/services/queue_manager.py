import frappe
from .netsuite import push_to_erp
from .invoice import create_sales_invoice_from_txn

def enqueue_transactions(mapped_data, log_name=None):
    """
    Takes the mapped transactions and queues them up for ERP processing.
    """
    for txn in mapped_data:
        frappe.enqueue(
            "teraoka_integration.teraoka_integration.services.queue_manager.process_single_transaction",
            queue='default',
            transaction_data=txn,
            log_name=log_name,
            timeout=300
        )

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
            if final_status == "Success":
                frappe.db.sql("""
                    UPDATE `tabTeraoka File Log` 
                    SET success_count = ifnull(success_count, 0) + 1 
                    WHERE name = %s
                """, (log_name,))
            else:
                txn_id = transaction_data.get('transaction_id')
                error_log = f"\\n[FAILED] TXN {txn_id}: {error_msg}"
                
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
                
        except Exception as e:
            frappe.log_error(title=f"Error updating Teraoka File Log {log_name}", message=frappe.get_traceback())
