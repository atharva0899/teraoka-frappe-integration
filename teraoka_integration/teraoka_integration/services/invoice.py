import frappe
from frappe import _
from frappe.utils import flt, nowdate, getdate

def create_sales_invoices(aggregated_items, settings, shop_code=None, posting_date=None):
	"""
	Transforms aggregated POS data into ERPNext Sales Invoices.
	Ensures strict 100-line limit per invoice.
	"""
	invoices = []
	error_count = 0
	items_list = list(aggregated_items.items())
	
	if not items_list:
		return {"invoices": [], "success_count": 0, "error_count": 0}
	
	# Split into chunks of 100 lines as per specification to prevent performance issues
	chunk_size = 100
	item_chunks = [items_list[i:i + chunk_size] for i in range(0, len(items_list), chunk_size)]
	
	warehouse = get_warehouse(settings, shop_code) or settings.default_warehouse
	
	for i, chunk in enumerate(item_chunks):
		positive_items = []
		negative_items = []
		
		# Separate normal sales and returns
		for item_code, values in chunk:
			qty = flt(values.get('qty'))
			if qty > 0:
				positive_items.append((item_code, values))
			elif qty < 0:
				negative_items.append((item_code, values))

		for items, is_return in [(positive_items, 0), (negative_items, 1)]:
			if not items:
				continue
				
			si = frappe.new_doc("Sales Invoice")
			si.company = settings.company
			si.customer = settings.customer # Book against default (Walk-In)
			si.posting_date = posting_date or nowdate()
			si.update_stock = 1 # Ensuring stock impact
			si.set_posting_time = 1
			si.teraoka_shop_code = shop_code
			
			if is_return:
				si.is_return = 1
			
			# Set Warehouse at global level if possible
			if warehouse:
				si.set_warehouse = warehouse
				
			items_added = 0
			chunk_error = 0
			
			for item_code, values in items:
				# Auto-Create missing Item on the fly to prevent integration failures
				if not frappe.db.exists("Item", item_code):
					try:
						new_item = frappe.new_doc("Item")
						new_item.item_code = item_code
						new_item.item_name = values.get('item_name') or item_code
						new_item.item_group = settings.default_item_group or "All Item Groups"
						new_item.stock_uom = "Nos"
						new_item.is_stock_item = 1
						new_item.insert(ignore_permissions=True)
						frappe.db.commit()
					except Exception as e:
						chunk_error += 1
						frappe.log_error(title=f"Teraoka Sync: Auto-Create Failed ({item_code})", message=str(e))
						continue

				si.append("items", {
					"item_code": item_code,
					"qty": flt(values.get('qty')),
					"rate": flt(values.get('rate')),
					"warehouse": warehouse,
					"allow_zero_valuation_rate": 1
				})
				items_added += 1
				
			if not si.items:
				error_count += chunk_error
				continue
				
			try:
				si.insert()
				if settings.auto_submit:
					try:
						si.submit()
					except Exception as e:
						# Keep it as draft if submission fails (e.g. Stock Ledger Error / Validation Error)
						frappe.log_error(title="Teraoka Sync: Auto-Submit Failed", message=str(e) + "\n\n" + frappe.get_traceback())
						
				invoices.append(si.name)
			except Exception as e:
				error_count += items_added
				frappe.log_error(title="Teraoka Sync: Invoice Creation Error", message=frappe.get_traceback())
				continue
			
	return {
		"invoices": invoices,
		"success_count": len(invoices),
		"error_count": error_count
	}

def get_warehouse(settings, shop_code):
	"""Finds mapping for a shop code from settings child table."""
	if not shop_code or not settings:
		return None
	for mapping in settings.get("shop_mappings", []):
		if mapping.shop_code == shop_code:
			return mapping.warehouse
	return None

def create_sales_invoice_from_txn(txn, settings):
	"""
	Transforms a single structured POS transaction (TL + ILs) into an ERPNext Sales Invoice.
	Supports splitting mixed transactions containing both positive and negative quantities.
	"""
	if not txn.get("items"):
		return {"status": "Failed", "error": "No items in transaction"}

	shop_code = txn.get("store_code")
	txn_id = txn.get("transaction_id", "Unknown")
	
	# Duplicate Check
	try:
		existing = frappe.db.get_value("Sales Invoice", {"teraoka_receipt_key": txn_id}, "name")
		if existing:
			return {"status": "Skipped", "error": f"Receipt {txn_id} already processed as {existing}"}
	except Exception:
		pass # Ignore if custom field is not migrated yet

	# Shop Mapping Resolution
	mapping = None
	for m in settings.get("shop_mappings", []):
		if m.shop_code == shop_code:
			mapping = m
			break
			
	warehouse = mapping.warehouse if mapping else settings.default_warehouse
	company = mapping.company if mapping and mapping.company else settings.company
	cost_center = mapping.cost_center if mapping else None

	# Customer Resolution
	customer = settings.customer
	customer_code = txn.get("customer_code")
	if customer_code:
		try:
			found_cust = frappe.db.get_value("Customer", {"teraoka_customer_code": customer_code}, "name")
			if found_cust:
				customer = found_cust
		except Exception:
			pass

	# Separate items into positive/zero and negative quantities with normalization for negative rates
	positive_items = []
	negative_items = []
	for item in txn.get("items"):
		qty = flt(item.get("qty"))
		rate = flt(item.get("rate"))
		
		# Normalize negative rate/amount to negative quantity and positive rate for ERPNext compatibility
		if rate < 0:
			qty = -qty
			rate = abs(rate)
			
		item_normalized = item.copy()
		item_normalized["qty"] = qty
		item_normalized["rate"] = rate

		if qty >= 0:
			positive_items.append(item_normalized)
		else:
			negative_items.append(item_normalized)

	created_invoices = []
	errors = []

	def build_invoice(items_to_add, is_ret, receipt_key_suffix=""):
		si = frappe.new_doc("Sales Invoice")
		si.company = company
		si.customer = customer
		si.posting_date = txn.get("date") or nowdate()
		si.update_stock = 1
		si.set_posting_time = 1
		si.teraoka_shop_code = shop_code
		
		try:
			si.teraoka_receipt_key = f"{txn_id}{receipt_key_suffix}"
		except Exception:
			pass
		
		if is_ret:
			si.is_return = 1
		
		suffix_desc = " (Return)" if is_ret else ""
		si.remarks = f"Auto-generated from Teraoka Integration{suffix_desc}.\nTransaction ID: {txn_id}\nStore Code: {shop_code}"
		
		if warehouse:
			si.set_warehouse = warehouse

		for item in items_to_add:
			item_barcode = item.get("item_code")
			item_code = frappe.db.get_value("Item Barcode", {"barcode": item_barcode}, "parent")
			if not item_code:
				if frappe.db.exists("Item", item_barcode):
					item_code = item_barcode
				else:
					raise Exception(f"Barcode not found in Item Master: {item_barcode}")

			si.append("items", {
				"item_code": item_code,
				"qty": flt(item.get("qty")),
				"rate": flt(item.get("rate")),
				"warehouse": warehouse,
				"cost_center": cost_center,
				"allow_zero_valuation_rate": 1
			})
		
		si.insert()
		if settings.auto_submit:
			si.submit()
			if settings.default_cash_account:
				create_payment_entry(si, settings)
		return si.name

	# 1. Create normal invoice
	if positive_items:
		try:
			inv_name = build_invoice(positive_items, is_ret=False)
			created_invoices.append(inv_name)
		except Exception as e:
			errors.append(str(e))
			frappe.log_error(title=f"Teraoka Sync: Normal Invoice Creation Error ({txn_id})", message=frappe.get_traceback())

	# 2. Create return invoice
	if negative_items:
		suffix = "-RET" if positive_items else ""
		ret_key = f"{txn_id}{suffix}"
		try:
			existing_ret = frappe.db.get_value("Sales Invoice", {"teraoka_receipt_key": ret_key}, "name")
			if not existing_ret:
				inv_name = build_invoice(negative_items, is_ret=True, receipt_key_suffix=suffix)
				created_invoices.append(inv_name)
			else:
				created_invoices.append(existing_ret)
		except Exception as e:
			errors.append(str(e))
			frappe.log_error(title=f"Teraoka Sync: Return Invoice Creation Error ({txn_id})", message=frappe.get_traceback())

	if errors:
		return {"status": "Failed", "error": "; ".join(errors)}
	
	if created_invoices:
		return {"status": "Success", "invoice": created_invoices[0]}
		
	return {"status": "Failed", "error": "No invoices created"}

def create_payment_entry(invoice, settings):
	"""
	Automatically creates and submits a Payment Entry for a Sales Invoice.
	Ensures the invoice is closed before NetSuite synchronization.
	Supports both standard payments and return/refund payments.
	"""
	try:
		pe = frappe.new_doc("Payment Entry")
		
		is_ret = flt(invoice.grand_total) < 0 or getattr(invoice, "is_return", 0)
		
		if is_ret:
			pe.payment_type = "Pay"
			pe.party_type = "Customer"
			pe.party = invoice.customer
			pe.company = invoice.company
			pe.posting_date = invoice.posting_date
			pe.paid_amount = abs(flt(invoice.grand_total))
			pe.received_amount = abs(flt(invoice.grand_total))
			pe.paid_from = settings.default_cash_account
			pe.paid_to = invoice.debit_to
		else:
			pe.payment_type = "Receive"
			pe.party_type = "Customer"
			pe.party = invoice.customer
			pe.company = invoice.company
			pe.posting_date = invoice.posting_date
			pe.paid_amount = invoice.grand_total
			pe.received_amount = invoice.grand_total
			pe.paid_from = invoice.debit_to
			pe.paid_to = settings.default_cash_account
		
		# Reference the invoice retaining negative signs for returns
		pe.append("references", {
			"reference_doctype": "Sales Invoice",
			"reference_name": invoice.name,
			"total_amount": invoice.grand_total,
			"outstanding_amount": invoice.grand_total,
			"allocated_amount": invoice.grand_total
		})
		
		pe.remarks = f"Automated payment for {invoice.name} via Teraoka Integration."
		pe.insert()
		pe.submit()
		return pe.name
	except Exception as e:
		frappe.log_error(title=f"Teraoka Sync: Payment Entry Error ({invoice.name})", message=frappe.get_traceback())
		return None
