import frappe
from frappe.model.document import Document
from frappe import _

class NetSuiteSyncLog(Document):
	pass


@frappe.whitelist()
def retry_sync(log_name):
    log = frappe.get_doc("NetSuite Sync Log", log_name)
    if log.status == "Success":
        frappe.throw(_("This record has already been successfully synchronized."))
        
    doc_type = log.document_type
    doc_name = log.document_name
    
    if doc_type == "Sales Invoice":
        from teraoka_integration.teraoka_integration.services.netsuite import push_to_erp
        res = push_to_erp(doc_name, file_log=log.file_log)
        if res.get("status") == "Success":
            log.db_set("status", "Success")
            log.db_set("error_message", "")
            if res.get("ns_id"):
                log.db_set("netsuite_id", res.get("ns_id"))
            frappe.msgprint(_("Sales Invoice synced successfully."))
            return "Success"
        else:
            frappe.throw(_("Sync failed: {0}").format(res.get("error")))
            
    elif doc_type == "Payment Entry":
        from teraoka_integration.teraoka_integration.services.netsuite import push_payment_to_erp
        pe = frappe.get_doc("Payment Entry", doc_name)
        invoice_name = None
        for ref in pe.references:
            if ref.reference_doctype == "Sales Invoice":
                invoice_name = ref.reference_name
                break
                
        if not invoice_name:
            frappe.throw(_("No linked Sales Invoice found for this Payment Entry."))
            
        netsuite_invoice_id = frappe.db.get_value("Sales Invoice", invoice_name, "netsuite_id")
        if not netsuite_invoice_id:
            frappe.throw(_("The linked Sales Invoice {0} must be synchronized to NetSuite first.").format(invoice_name))
            
        res = push_payment_to_erp(doc_name, netsuite_invoice_id, file_log=log.file_log)
        if res.get("status") == "Success":
            log.db_set("status", "Success")
            log.db_set("error_message", "")
            if res.get("ns_id"):
                log.db_set("netsuite_id", res.get("ns_id"))
            frappe.msgprint(_("Payment Entry synced successfully."))
            return "Success"
        else:
            frappe.throw(_("Sync failed: {0}").format(res.get("error")))
            
    else:
        frappe.throw(_("Unsupported document type: {0}").format(doc_type))

