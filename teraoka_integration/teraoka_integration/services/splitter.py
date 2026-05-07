import frappe

def group_transactions(raw_lines):
    """
    Groups Item Lines (IL) under their respective Transaction Lines (TL).
    Also supports I1 (Header) and I3 (Item) groupings if applicable.
    """
    transactions = []
    current_txn = None
    
    for row in raw_lines:
        if not row: continue
        
        record_type = row[0]
        
        # TL or I1 are transaction headers
        if record_type in ("TL", "I1"):
            current_txn = {
                "header": row,
                "items": []
            }
            transactions.append(current_txn)
            
        # IL or I3 are item records
        elif record_type in ("IL", "I3") and current_txn is not None:
            current_txn["items"].append(row)
            
    return transactions
