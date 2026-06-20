import frappe
import requests
import json

def format_error_message(msg):
    """Parses raw JSON error messages from NetSuite/ERPNext and returns a clean, human-readable description."""
    if not msg:
        return ""
    msg_str = str(msg).strip()
    if msg_str.startswith("{") and msg_str.endswith("}"):
        try:
            import json
            data = json.loads(msg_str)
            # NetSuite OData standard errors
            if "o:errorDetails" in data and isinstance(data["o:errorDetails"], list) and len(data["o:errorDetails"]) > 0:
                details = [d.get("detail") for d in data["o:errorDetails"] if d.get("detail")]
                if details:
                    return "; ".join(details)
            elif "error" in data and isinstance(data["error"], dict) and "message" in data["error"]:
                return data["error"]["message"]
            elif "detail" in data:
                return data["detail"]
            elif "title" in data:
                return data["title"]
        except Exception:
            pass
    return msg_str

def send_google_chat_notification(log, webhook_url, success_count=None, error_count=None, is_netsuite_sync=False):
    """Sends a professional card notification to Google Chat."""
    import requests
    
    # Check alert cooldown to prevent fatigue
    cache_key = f"google_chat_alert_cooldown:{log.name}"
    if frappe.cache().get_value(cache_key):
        return 0, "Alert throttled (cooldown active)"
        
    is_failed = log.status == "Failed"
    if is_netsuite_sync:
        title_text = "NetSuite Sync Failed" if is_failed else "NetSuite Sync Partial Success"
    else:
        title_text = "ERPNext POS Import Failed" if is_failed else "ERPNext POS Import Warning"
        
    image_url = "https://img.icons8.com/color/96/000000/cancel--v1.png" if is_failed else "https://img.icons8.com/color/96/000000/warning-shield.png"
    
    erpnext_url = f"{frappe.utils.get_url()}/app/teraoka-file-log/{log.name}"
    
    # Retrieve top 3 errors from in-memory transaction details to avoid DB save latency
    error_widgets = []
    if is_failed or log.status in ("Partial Success", "Pending Sync"):
        errors = []
        for d in log.get("transaction_details") or []:
            if d.status == "Failed" and d.error_message:
                errors.append(d.error_message)
        
        unique_errors = list(dict.fromkeys(errors))[:3]
        
        if unique_errors:
            formatted_errors = []
            for err in unique_errors:
                clean_err = format_error_message(err)
                if clean_err:
                    formatted_errors.append(f"• {clean_err}")
            if formatted_errors:
                error_text = "<br>".join(formatted_errors)
                error_widgets.append({
                    "decoratedText": {
                        "topLabel": "Top Errors",
                        "text": f"<font color=\"#d93025\">{error_text}</font>",
                        "wrapText": True
                    }
                })
                
    sections = [
        {
            "header": "Processing Details",
            "widgets": [
                {
                    "decoratedText": {
                        "topLabel": "File Name",
                        "text": f"<b>{log.filename}</b>"
                    }
                },
                {
                    "decoratedText": {
                        "topLabel": "Shop Code & Date",
                        "text": f"Shop <b>{log.shop_code}</b> | {log.file_date}"
                    }
                }
            ]
        }
    ]
    
    if error_widgets:
        sections.append({
            "header": "Error Details",
            "widgets": error_widgets
        })
        
    display_success = success_count if success_count is not None else log.success_count
    display_error = error_count if error_count is not None else log.error_count

    sections.append({
        "header": "Sync Statistics",
        "widgets": [
            {
                "decoratedText": {
                    "topLabel": "Successful Invoices",
                    "text": f"<font color=\"#1e8e3e\"><b>{display_success}</b></font>"
                }
            },
            {
                "decoratedText": {
                    "topLabel": "Failed Invoices",
                    "text": f"<font color=\"#d93025\"><b>{display_error}</b></font>"
                }
            },
            {
                "buttonList": {
                    "buttons": [
                        {
                            "text": "View Details in ERPNext",
                            "onClick": {
                                "openLink": {
                                    "url": erpnext_url
                                }
                            }
                        }
                    ]
                }
            }
        ]
    })
    
    payload = {
        "cardsV2": [
            {
                "cardId": f"teraoka-sync-{log.name}",
                "card": {
                    "header": {
                        "title": title_text,
                        "subtitle": "Teraoka POS Integration",
                        "imageUrl": image_url,
                        "imageType": "CIRCLE"
                    },
                    "sections": sections
                }
            }
        ]
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.ok:
            # Set cooldown for 4 hours (14400 seconds) to prevent webhook spam
            frappe.cache().set_value(cache_key, 1, expires_in_sec=14400)
            return 1, ""
        return 0, f"HTTP {response.status_code}: {response.text}"
    except Exception as e:

        err_msg = str(e)
        frappe.logger("teraoka").error(f"Google Chat webhook failed: {err_msg}")
        return 0, err_msg

@frappe.whitelist()
def send_daily_sync_summary():
    """Aggregates daily sync stats and sends a summary to Google Chat."""
    import requests
    from frappe.utils import today, get_url
    
    settings = frappe.get_single("Teraoka Settings")
    if not settings.google_chat_webhook_url:
        return
        
    current_date = today()
    
    # Aggregate data for today
    stats = frappe.db.sql("""
        SELECT 
            COUNT(name) as total_files,
            SUM(total_amount) as total_revenue
        FROM `tabTeraoka File Log`
        WHERE DATE(creation) = %s
    """, current_date, as_dict=True)[0]
    
    total_files = stats.get("total_files") or 0
    if total_files == 0:
        return # Nothing processed today
        
    total_revenue = stats.get("total_revenue") or 0.0
    
    # Calculate actual NetSuite sync stats for today's file logs
    total_success = frappe.db.sql("""
        SELECT COUNT(distinct d.doc_name)
        FROM `tabTeraoka File Log Detail` d
        JOIN `tabTeraoka File Log` p ON d.parent = p.name
        WHERE DATE(p.creation) = %s 
          AND d.doc_type = 'Sales Invoice' 
          AND d.status = 'Success'
          AND EXISTS (
              SELECT 1 FROM `tabSales Invoice` si 
              WHERE si.name = d.doc_name 
                AND si.netsuite_id IS NOT NULL 
                AND si.netsuite_id != ''
          )
    """, current_date)[0][0] or 0

    total_errors = frappe.db.sql("""
        SELECT COUNT(distinct d.doc_name)
        FROM `tabTeraoka File Log Detail` d
        JOIN `tabTeraoka File Log` p ON d.parent = p.name
        WHERE DATE(p.creation) = %s 
          AND d.doc_type = 'Sales Invoice'
          AND d.status = 'Failed'
          AND d.doc_name IS NOT NULL AND d.doc_name != ''
    """, current_date)[0][0] or 0
    
    # Format the payload
    has_errors = total_errors > 0
    title_text = "Daily Sync Summary"
    image_url = "https://img.icons8.com/color/96/000000/combo-chart--v1.png"
    
    erpnext_url = f"{get_url()}/app/teraoka-file-log"
    
    payload = {
        "cardsV2": [
            {
                "cardId": f"daily-summary-{current_date}",
                "card": {
                    "header": {
                        "title": title_text,
                        "subtitle": f"Teraoka Integration - {current_date}",
                        "imageUrl": image_url,
                        "imageType": "CIRCLE"
                    },
                    "sections": [
                        {
                            "header": "End of Day Statistics",
                            "widgets": [
                                {
                                    "decoratedText": {
                                        "topLabel": "Files Processed",
                                        "text": f"<b>{total_files}</b>"
                                    }
                                },
                                {
                                    "decoratedText": {
                                        "topLabel": "Total Revenue Synced",
                                        "text": f"<b>{frappe.utils.fmt_money(total_revenue)}</b>"
                                    }
                                },
                                {
                                    "decoratedText": {
                                        "topLabel": "Successful Invoices",
                                        "text": f"<font color=\"#1e8e3e\"><b>{total_success}</b></font>"
                                    }
                                },
                                {
                                    "decoratedText": {
                                        "topLabel": "Failed Invoices",
                                        "text": f"<font color=\"{ '#d93025' if has_errors else '#1e8e3e' }\"><b>{total_errors}</b></font>"
                                    }
                                },
                                {
                                    "buttonList": {
                                        "buttons": [
                                            {
                                                "text": "View All Logs in ERPNext",
                                                "onClick": {
                                                    "openLink": {
                                                        "url": erpnext_url
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    ]
                }
            }
        ]
    }
    
    try:
        requests.post(settings.google_chat_webhook_url, json=payload, timeout=10)
    except Exception as e:
        frappe.logger("teraoka").error(f"Failed to send daily summary to Google Chat: {e}")
