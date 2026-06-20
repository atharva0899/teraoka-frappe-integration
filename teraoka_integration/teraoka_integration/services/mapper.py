import frappe
from frappe.utils import getdate
import datetime
from .parser import clean_float

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
        store_code = header[1].strip() if len(header) > 1 else "Default"
        date_str = header[2].strip() if len(header) > 2 else ""
        register_no = header[4].strip() if len(header) > 4 else "00"
        receipt_no = header[5].strip() if len(header) > 5 else "00"
        txn_id = f"{store_code}_{date_str}_{register_no}_{receipt_no}"
        
        customer_code = header[11].strip() if len(header) > 11 else ""
        customer_name = header[12].strip() if len(header) > 12 else ""
        
        # Format date YYYYMMDD -> YYYY-MM-DD
        formatted_date = None
        if len(date_str) >= 8:
            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            
        grand_total = clean_float(header[30] if len(header) > 30 else "0")
        tax_amount = clean_float(header[43] if len(header) > 43 else "0")
        is_return = grand_total < 0
        
        mapped_txn = {
            "transaction_id": txn_id,
            "store_code": store_code,
            "date": formatted_date,
            "register": register_no,
            "receipt": receipt_no,
            "customer_code": customer_code,
            "customer_name": customer_name,
            "grand_total": grand_total,
            "tax_amount": tax_amount,
            "is_return": is_return,
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
                rate = amount / qty if qty else 0.0
            else:
                # IL mapping (LGYOUMU)
                item_code = item[18].strip() if len(item) > 18 else "Unknown"
                item_name = item[19].strip() if len(item) > 19 else "Unknown Item"
                qty = clean_float(item[14] if len(item) > 14 and item[14].strip() else "1")
                rate = clean_float(item[20] if len(item) > 20 and item[20].strip() else "0")
                amount = qty * rate
                
            mapped_txn["items"].append({
                "item_code": item_code,
                "item_name": item_name,
                "qty": qty,
                "amount": amount,
                "rate": rate
            })
            
        mapped_data.append(mapped_txn)
        
    return mapped_data
