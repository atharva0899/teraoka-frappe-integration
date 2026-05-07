import frappe
from frappe.utils import getdate
import datetime

def clean_float(val):
    """Robust numeric cleaner for POS data."""
    if val is None: return 0.0
    s_val = str(val).strip()
    if not s_val: return 0.0
    cleaned = "".join(c for c in s_val if c.isdigit() or c in ".-")
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0

def map_transactions(grouped_transactions):
    """
    Maps the raw grouped TL->IL data into structured dictionaries
    ready for Queue Processing or ERP Push.
    """
    mapped_data = []
    
    for txn in grouped_transactions:
        header = txn.get("header", [])
        items = txn.get("items", [])
        
        if not header: continue
        
        record_type = header[0]
        
        # LGYOUMU TL / I1 Header Line
        # Example: TL, 001, 20260420, 000001
        store_code = header[1].strip() if len(header) > 1 else "Default"
        date_str = header[2].strip() if len(header) > 2 else ""
        txn_id = header[3].strip() if len(header) > 3 else ""
        
        # Format date YYYYMMDD -> YYYY-MM-DD
        formatted_date = None
        if len(date_str) == 8:
            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            
        mapped_txn = {
            "transaction_id": txn_id,
            "store_code": store_code,
            "date": formatted_date,
            "items": []
        }
        
        for item in items:
            if not item: continue
            
            item_type = item[0]
            
            # Extract standard fields based on record type
            if item_type == "I3":
                item_code = item[16].strip() if len(item) > 16 else "Unknown"
                item_name = item[19].strip() if len(item) > 19 else "Unknown Item"
                qty = clean_float(item[20] if len(item) > 20 else "1")
                amount = clean_float(item[22] if len(item) > 22 else "0")
            else:
                # IL mapping (LGYOUMU)
                item_code = item[16].strip() if len(item) > 16 else "Unknown"
                item_name = item[19].strip() if len(item) > 19 else "Unknown Item"
                qty = clean_float(item[14] if len(item) > 14 else "1")
                amount = clean_float(item[21] if len(item) > 21 else "0")
                
            mapped_txn["items"].append({
                "item_code": item_code,
                "item_name": item_name,
                "qty": qty,
                "amount": amount,
                "rate": amount / qty if qty else 0.0
            })
            
        mapped_data.append(mapped_txn)
        
    return mapped_data
