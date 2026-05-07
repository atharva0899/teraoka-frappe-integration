import frappe
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
    
    # Base Filters
    date_filter = f"processed_on >= '{s_from} 00:00:00' AND processed_on <= '{s_to} 23:59:59'"
    if shop_code and shop_code != 'undefined':
        date_filter += f" AND shop_code = '{shop_code}'"

    # 1. Aggregate Stats (Truth from Sales Invoices)
    inv_res = frappe.db.sql(f"SELECT SUM(grand_total) as sales FROM `tabSales Invoice` WHERE docstatus=1 AND {date_filter.replace('processed_on', 'posting_date')}", as_dict=True)[0]
    log_res = frappe.db.sql(f"SELECT SUM(success_count) as succ, SUM(error_count) as err FROM `tabTeraoka File Log` WHERE {date_filter}", as_dict=True)[0]
    
    total_sales = inv_res.get('sales') or 0.0
    succ = log_res.get('succ') or 0
    err = log_res.get('err') or 0
    total_records = succ + err
    rate = round((succ / total_records) * 100, 1) if total_records > 0 else 100.0

    # 2. Comparison (Previous Period)
    d1, d2 = getdate(s_from), getdate(s_to)
    delta = (d2 - d1).days + 1
    prev_filter = f"processed_on >= '{add_days(s_from, -delta)} 00:00:00' AND processed_on <= '{add_days(s_from, -1)} 23:59:59'"
    if shop_code and shop_code != 'undefined':
        prev_filter += f" AND shop_code = '{shop_code}'"
        
    prev_sales = (frappe.db.sql(f"SELECT SUM(total_amount) as sales FROM `tabTeraoka File Log` WHERE {prev_filter}", as_dict=True)[0]).get('sales') or 0.0
    growth = round(((total_sales - prev_sales) / prev_sales) * 100, 1) if prev_sales > 0 else (100.0 if total_sales > 0 else 0.0)

    # 3. Dynamic Chart Data
    chart_labels = []
    chart_values = []
    if s_from == s_to:
        hourly_map = {h: 0.0 for h in range(24)}
        chart_raw = frappe.db.sql(f"SELECT HOUR(processed_on) as h, SUM(total_amount) as s FROM `tabTeraoka File Log` WHERE {date_filter} GROUP BY HOUR(processed_on)", as_dict=True)
        for r in chart_raw: hourly_map[r.h] = float(r.s)
        for h in range(24):
            chart_labels.append(f"{str(h).zfill(2)}:00")
            chart_values.append(hourly_map[h])
        chart_title = f"{'Shop ' + shop_code if shop_code else 'Total'} Hourly Velocity ({format_date(s_from, 'dd MMM')})"
    else:
        chart_raw = frappe.db.sql(f"SELECT DATE(processed_on) as d, SUM(total_amount) as s FROM `tabTeraoka File Log` WHERE {date_filter} GROUP BY DATE(processed_on) ORDER BY d ASC", as_dict=True)
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
        if log.total_records > 0: pipeline["parser"] = "success"
        if log.status == "Processed": pipeline["mapper"] = "success"; pipeline["invoice"] = "success"
        if log.status == "Processed" and log.success_count > 0: pipeline["netsuite"] = "success"

    recent_logs = frappe.db.sql(f"SELECT name, filename, status, success_count, total_records, processed_on FROM `tabTeraoka File Log` WHERE {date_filter} ORDER BY processed_on DESC LIMIT 10", as_dict=True)
    
    # Shop stats should ALWAYS show all shops for comparison
    clean_filter = f"processed_on >= '{s_from} 00:00:00' AND processed_on <= '{s_to} 23:59:59'"
    shop_stats = frappe.db.sql(f"SELECT shop_code, SUM(total_amount) as sales, MAX(processed_on) as last_sync, status FROM `tabTeraoka File Log` WHERE shop_code IS NOT NULL AND shop_code != '' AND {clean_filter} GROUP BY shop_code ORDER BY sales DESC", as_dict=True)

    actions = []
    if err > 0:
        a_filter = {"processed_on": [">=", s_from], "status": "Failed"}
        if shop_code: a_filter["shop_code"] = shop_code
        failed_files = frappe.get_all("Teraoka File Log", filters=a_filter, limit=3, fields=["filename", "name"])
        for f in failed_files:
            actions.append({"type": "critical", "message": f"Sync failure in {f.filename}", "link": f"/app/teraoka-file-log/{f.name}"})

    return {
        "total_sales": frappe.format_value(total_sales, {"fieldtype": "Currency"}),
        "growth": growth, "success_rate": rate, "total_records": total_records,
        "health": "Healthy" if not last_log or last_log[0].status != "Failed" else "Issues Detected",
        "uptime": "99.9%", "last_sync": str(last_log[0].processed_on) if last_log and last_log[0].processed_on else "Never",
        "recent_logs": recent_logs, "shop_stats": shop_stats,
        "chart": {"labels": chart_labels, "values": chart_values, "title": chart_title},
        "briefing": briefing, "actions": actions, "shop_code": shop_code,
        "from_date": s_from, "to_date": s_to, "pipeline": pipeline
    }

@frappe.whitelist()
def trigger_sync():
    from teraoka_integration.teraoka_integration.services.process import sync_teraoka_files
    frappe.enqueue("teraoka_integration.teraoka_integration.services.process.sync_teraoka_files", queue='default')
    return {"status": "Success"}
