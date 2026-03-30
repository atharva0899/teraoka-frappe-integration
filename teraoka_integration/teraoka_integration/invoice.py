import frappe
from frappe import _
from frappe.utils import flt, nowdate, getdate

def create_sales_invoices(data, settings, shop_code=None, posting_date=None):
	"""Transforms aggregated POS data into ERPNext Sales Invoices."""
	invoices = []
	error_count = 0
	items_list = list(data.items())
	
	if not items_list:
		return {"invoices": [], "success_count": 0, "error_count": 0}
	
	# Split items if they exceed 100
	chunk_size = 100
	item_chunks = [items_list[i:i + chunk_size] for i in range(0, len(items_list), chunk_size)]
	
	warehouse = get_warehouse(shop_code) or settings.default_warehouse
	
	for i, chunk in enumerate(item_chunks):
		si = frappe.new_doc("Sales Invoice")
		si.company = settings.company
		si.customer = settings.customer
		si.posting_date = posting_date or nowdate()
		si.update_stock = 1
		si.set_posting_time = 1
		
		# Set Warehouse at global level if possible, else per item
		if warehouse:
			si.set_warehouse = warehouse
			
		items_added = 0
		for item_code, values in chunk:
			# Check if item exists in ERPNext
			if not frappe.db.exists("Item", item_code):
				error_count += 1
				frappe.log_error(f"Missing Item: {item_code}", "Teraoka Integration")
				continue
				
			si.append("items", {
				"item_code": item_code,
				"qty": flt(values['qty']),
				"rate": flt(values['rate']),
				"warehouse": warehouse
			})
			items_added += 1
			
		if not si.items:
			continue
			
		try:
			si.insert()
			if settings.auto_submit:
				si.submit()
			invoices.append(si.name)
		except Exception as e:
			error_count += items_added
			frappe.log_error(f"Invoice Creation Failed: {str(e)}", "Teraoka Integration")
			continue
			
	return {
		"invoices": invoices,
		"success_count": len(invoices),
		"error_count": error_count
	}

def get_warehouse(shop_code):
	"""Finds mapping for a shop code."""
	if not shop_code:
		return None
	return frappe.db.get_value("Teraoka Shop Mapping", {"shop_code": shop_code}, "warehouse")
