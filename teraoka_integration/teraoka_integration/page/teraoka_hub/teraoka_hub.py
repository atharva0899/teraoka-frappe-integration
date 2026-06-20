import os
import frappe
from frappe import _
from frappe.utils import add_days, nowdate, getdate, format_date

@frappe.whitelist()
def get_dashboard_data(from_date=None, to_date=None, shop_code=None):
    # Standardize dates
    if not from_date or from_date in ['undefined', 'null', 'None']:
        from_date = nowdate()
    if not to_date or to_date in ['undefined', 'null', 'None']:
        to_date = nowdate()
    
    s_from = str(from_date).split(' ')[0]
    s_to = str(to_date).split(' ')[0]
    
    # 1. Aggregate Stats (Truth from Sales Invoices)
    inv_conditions = ["docstatus = 1", "posting_date >= %s", "posting_date <= %s"]
    inv_params = [s_from, s_to]
    if shop_code and shop_code != 'undefined':
        inv_conditions.append("teraoka_shop_code = %s")
        inv_params.append(shop_code)
        
    inv_query = f"SELECT SUM(grand_total) as sales FROM `tabSales Invoice` WHERE {' AND '.join(inv_conditions)}"
    inv_res = frappe.db.sql(inv_query, tuple(inv_params), as_dict=True)[0]
    
    log_conditions = ["processed_on >= %s", "processed_on <= %s"]
    log_params = [f"{s_from} 00:00:00", f"{s_to} 23:59:59"]
    if shop_code and shop_code != 'undefined':
        log_conditions.append("shop_code = %s")
        log_params.append(shop_code)
        
    log_query = f"SELECT SUM(success_count) as succ, SUM(error_count) as err FROM `tabTeraoka File Log` WHERE {' AND '.join(log_conditions)}"
    log_res = frappe.db.sql(log_query, tuple(log_params), as_dict=True)[0]
    
    total_sales = inv_res.get('sales') or 0.0
    succ = log_res.get('succ') or 0
    err = log_res.get('err') or 0
    total_records = succ + err
    rate = round((succ / total_records) * 100, 1) if total_records > 0 else 100.0

    # 2. Comparison (Previous Period)
    d1, d2 = getdate(s_from), getdate(s_to)
    delta = (d2 - d1).days + 1
    
    prev_conditions = ["processed_on >= %s", "processed_on <= %s"]
    prev_params = [f"{add_days(s_from, -delta)} 00:00:00", f"{add_days(s_from, -1)} 23:59:59"]
    if shop_code and shop_code != 'undefined':
        prev_conditions.append("shop_code = %s")
        prev_params.append(shop_code)
        
    prev_query = f"SELECT SUM(total_amount) as sales FROM `tabTeraoka File Log` WHERE {' AND '.join(prev_conditions)}"
    prev_sales = (frappe.db.sql(prev_query, tuple(prev_params), as_dict=True)[0]).get('sales') or 0.0
    growth = round(((total_sales - prev_sales) / prev_sales) * 100, 1) if prev_sales > 0 else (100.0 if total_sales > 0 else 0.0)

    # 3. Dynamic Chart Data
    chart_labels = []
    chart_values = []
    
    chart_conditions = ["processed_on >= %s", "processed_on <= %s"]
    chart_params = [f"{s_from} 00:00:00", f"{s_to} 23:59:59"]
    if shop_code and shop_code != 'undefined':
        chart_conditions.append("shop_code = %s")
        chart_params.append(shop_code)
        
    if s_from == s_to:
        hourly_map = {h: 0.0 for h in range(24)}
        chart_query = f"SELECT HOUR(processed_on) as h, SUM(total_amount) as s FROM `tabTeraoka File Log` WHERE {' AND '.join(chart_conditions)} GROUP BY HOUR(processed_on)"
        chart_raw = frappe.db.sql(chart_query, tuple(chart_params), as_dict=True)
        for r in chart_raw: hourly_map[r.h] = float(r.s)
        for h in range(24):
            chart_labels.append(f"{str(h).zfill(2)}:00")
            chart_values.append(hourly_map[h])
        chart_title = f"{'Shop ' + shop_code if shop_code else 'Total'} Hourly Velocity ({format_date(s_from, 'dd MMM')})"
    else:
        chart_query = f"SELECT DATE(processed_on) as d, SUM(total_amount) as s FROM `tabTeraoka File Log` WHERE {' AND '.join(chart_conditions)} GROUP BY DATE(processed_on) ORDER BY d ASC"
        chart_raw = frappe.db.sql(chart_query, tuple(chart_params), as_dict=True)
        if not chart_raw:
            chart_labels = [format_date(s_from, "dd MMM"), format_date(s_to, "dd MMM")]
            chart_values = [0.0, 0.0]
        else:
            chart_labels = [format_date(str(r.d), "dd MMM") for r in chart_raw]
            chart_values = [float(r.s) for r in chart_raw]
        chart_title = f"{'Shop ' + shop_code if shop_code else 'Global'} Velocity Trend"
        
    # 4. AI Executive Briefing
    briefing = []
    scope_text = f"for Shop {shop_code}" if shop_code else "across all nodes"
    
    if total_sales > 0:
        perf_text = "exceeding" if growth > 0 else "trailing"
        briefing.append(f"Performance {scope_text} is {perf_text} the previous period by {abs(growth)}%.")
    else:
        briefing.append(f"No transactions detected {scope_text} during this interval.")
        
    if err > 0:
        briefing.append(f"Warning: {err} anomalies detected. High-priority resolution required in the Action Center.")
    else:
        briefing.append("System integrity is optimal. All ingestion stages are performing within parameters.")

    # 5. Pipeline & Data
    settings = frappe.get_single("Teraoka Settings")
    last_log_filter = {"shop_code": shop_code} if shop_code else {}
    last_log = frappe.get_all("Teraoka File Log", filters=last_log_filter, order_by="creation desc", limit=1, fields=["status", "processed_on", "total_records", "success_count", "error_count"])
    
    pipeline = {"sftp": "active" if settings.enabled else "pending", "parser": "pending", "mapper": "pending", "invoice": "pending", "netsuite": "pending"}
    if last_log:
        log = last_log[0]
        # parser stage
        if log.total_records > 0 or log.status in ("Pending Sync", "Success", "Partial Success"):
            pipeline["parser"] = "success"
        elif log.status == "Failed":
            pipeline["parser"] = "error"
            
        # mapper and invoice stages
        if log.status == "Pending":
            pipeline["mapper"] = "active"
        elif log.status in ("Pending Sync", "Success", "Partial Success"):
            pipeline["mapper"] = "success"
            pipeline["invoice"] = "success"
        elif log.status == "Failed":
            if log.total_records > 0:
                pipeline["mapper"] = "success"
                pipeline["invoice"] = "error" if log.success_count == 0 else "success"
            else:
                pipeline["mapper"] = "error"
                
        # netsuite stage
        if log.status == "Pending Sync":
            pipeline["netsuite"] = "active"
        elif log.status == "Success":
            pipeline["netsuite"] = "success"
        elif log.status == "Partial Success":
            pipeline["netsuite"] = "error"  # error indicates there are some issues to address
        elif log.status == "Failed" and log.total_records > 0:
            pipeline["netsuite"] = "error"

    recent_conditions = ["processed_on >= %s", "processed_on <= %s"]
    recent_params = [f"{s_from} 00:00:00", f"{s_to} 23:59:59"]
    if shop_code and shop_code != 'undefined':
        recent_conditions.append("shop_code = %s")
        recent_params.append(shop_code)
        
    recent_query = f"SELECT name, filename, status, success_count, total_records, processed_on FROM `tabTeraoka File Log` WHERE {' AND '.join(recent_conditions)} ORDER BY processed_on DESC LIMIT 10"
    recent_logs = frappe.db.sql(recent_query, tuple(recent_params), as_dict=True)
    
    # Shop stats should ALWAYS show all shops for comparison
    shop_conditions = ["shop_code IS NOT NULL", "shop_code != ''", "processed_on >= %s", "processed_on <= %s"]
    shop_params = [f"{s_from} 00:00:00", f"{s_to} 23:59:59"]
    shop_query = f"""
        SELECT 
            shop_code, 
            SUM(total_amount) as sales, 
            MAX(processed_on) as last_sync,
            (SELECT status FROM `tabTeraoka File Log` 
             WHERE shop_code = l.shop_code 
             ORDER BY processed_on DESC LIMIT 1) as status
        FROM `tabTeraoka File Log` l 
        WHERE {' AND '.join(shop_conditions)} 
        GROUP BY shop_code 
        ORDER BY sales DESC
    """
    shop_stats = frappe.db.sql(shop_query, tuple(shop_params), as_dict=True)

    actions = []
    if err > 0:
        a_filter = {"processed_on": [">=", s_from], "status": "Failed"}
        if shop_code: a_filter["shop_code"] = shop_code
        failed_files = frappe.get_all("Teraoka File Log", filters=a_filter, limit=3, fields=["filename", "name"])
        for f in failed_files:
            actions.append({"type": "critical", "message": f"Sync failure in {f.filename}", "link": f"/app/teraoka-file-log/{f.name}", "log_name": f.name})

    # 6. Active Queue Details (files currently processing or pending sync to NetSuite)
    queue_res = frappe.db.sql("""
        SELECT 
            SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) as processing,
            SUM(CASE WHEN status = 'Pending Sync' THEN 1 ELSE 0 END) as pending_sync
        FROM `tabTeraoka File Log`
    """, as_dict=True)[0]
    
    processing_count = queue_res.get("processing") or 0
    pending_sync_count = queue_res.get("pending_sync") or 0

    return {
        "total_sales": frappe.format_value(total_sales, {"fieldtype": "Currency"}),
        "growth": growth, "success_rate": rate, "total_records": total_records,
        "health": "Healthy" if not last_log or last_log[0].status != "Failed" else "Issues Detected",
        "uptime": "99.9%", "last_sync": str(last_log[0].processed_on) if last_log and last_log[0].processed_on else "Never",
        "recent_logs": recent_logs, "shop_stats": shop_stats,
        "chart": {"labels": chart_labels, "values": chart_values, "title": chart_title},
        "briefing": briefing, "actions": actions, "shop_code": shop_code,
        "from_date": s_from, "to_date": s_to, "pipeline": pipeline,
        "processing_count": processing_count, "pending_sync_count": pending_sync_count
    }

@frappe.whitelist()
def trigger_sync():
    from teraoka_integration.teraoka_integration.services.process import sync_teraoka_files
    frappe.enqueue("teraoka_integration.teraoka_integration.services.process.sync_teraoka_files", queue='default')
    return {"status": "Success"}

@frappe.whitelist()
def run_connectivity_diagnostics():
    settings = frappe.get_single("Teraoka Settings")
    
    # 1. Test SFTP/FTP
    sftp_status = "Success"
    sftp_message = "Connected successfully."
    try:
        from teraoka_integration.teraoka_integration.services.ftp import list_files
        list_files(settings)
    except Exception as e:
        sftp_status = "Failed"
        sftp_message = str(e)
        
    # 2. Test NetSuite
    from teraoka_integration.teraoka_integration.services.netsuite import NetSuiteConnector
    connector = NetSuiteConnector(settings)
    ns_res = connector.test_connection()
    
    return {
        "sftp": {"status": sftp_status, "message": sftp_message},
        "netsuite": ns_res
    }

@frappe.whitelist()
def reprocess_file(log_name):
    """Manually triggers processing of a previously logged file."""
    log = frappe.get_doc("Teraoka File Log", log_name)
    local_path = os.path.join(frappe.get_site_path("private", "files"), log.filename)
    
    # If the local file has been removed/archived, download it again
    if not os.path.exists(local_path):
        try:
            settings = frappe.get_single("Teraoka Settings")
            from teraoka_integration.teraoka_integration.services.ftp import download_file
            download_file(settings, log.filename, local_path)
        except Exception as e:
            frappe.throw(_("Failed to download file from POS server for reprocessing: {0}").format(str(e)))
            
    # Update log status to Pending and clear error counts/logs/details
    log.status = "Pending"
    log.error_count = 0
    log.success_count = 0
    log.logs = ""
    # Clear child table details safely using db calls or document API
    log.transaction_details = []
    log.save(ignore_permissions=True)
    frappe.db.commit()
    
    frappe.enqueue(
        "teraoka_integration.teraoka_integration.services.process.process_file",
        queue="default",
        filename=log.filename,
        log_name=log.name
    )
    return {"status": "Success"}
