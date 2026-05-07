import os
import frappe
from frappe import _
from frappe.utils import now_datetime, getdate, add_years
from .ftp import list_files, download_file, archive_file, TeraokaConnector
from .parser import parse_csv
from .invoice import create_sales_invoices
import re

@frappe.whitelist()
def sync_teraoka_files():
	"""Main entry point for syncing Teraoka POS files."""
	settings = frappe.get_single("Teraoka Settings")
	if not settings.enabled:
		return
	
	try:
		with TeraokaConnector(settings) as tconn:
			files = list_files(settings, conn_obj=tconn)
			
			if not files:
				return
				
			for filename in files:
				# Skip hidden files
				if filename.startswith("."):
					continue
				
				# Process .csv files OR GYOUMU files (OGYOUMU.001, etc) OR the specific 'test_data' file
				if filename.endswith(".csv") or "GYOUMU" in filename.upper() or filename == "test_data":
					# Try to get existing log or create new one
					log_name = frappe.db.get_value("Teraoka File Log", 
						{"filename": filename, "processed_on": [">=", getdate()]}, "name")
					
					if log_name:
						log = frappe.get_doc("Teraoka File Log", log_name)
						if log.status in ("Success", "Pending Sync"):
							continue
					else:
						log = frappe.new_doc("Teraoka File Log")
						log.filename = filename
						log.status = "Pending"
						log.insert()
					
					# Download immediately
					local_path = os.path.join(frappe.get_site_path("private", "files"), filename)
					download_file(settings, filename, local_path, conn_obj=tconn)
					attach_file_to_log(filename, local_path, log)

					# Queue for Processing
					frappe.enqueue(
						"teraoka_integration.teraoka_integration.services.process.process_file",
						queue="default",
						filename=filename,
						log_name=log.name
					)
				
	except Exception as e:
		frappe.log_error(title="Teraoka Sync: Connection Failed", message=frappe.get_traceback())

def process_file(filename, log_name):
	"""Processes a single file and populates MIS analytics summary."""
	log = frappe.get_doc("Teraoka File Log", log_name)
	settings = frappe.get_single("Teraoka Settings")
	local_path = os.path.join(frappe.get_site_path("private", "files"), filename)
	
	try:
		# Parse with summary support (Legacy/Fallback)
		result_data = parse_csv(local_path)
		data = result_data.get("items", {})
		summary = result_data.get("summary", {})
		
		# New Architecture: Raw -> Split -> Map -> Queue
		from .parser import parse_raw_lines
		from .splitter import group_transactions
		from .mapper import map_transactions
		from .queue_manager import enqueue_transactions
		
		raw_lines = parse_raw_lines(local_path)
		grouped_txns = group_transactions(raw_lines)
		mapped_data = map_transactions(grouped_txns)
		
		# Metadata Extraction
		shop_code = filename.split("_")[0] if "_" in filename else "Default"
		if "GYOUMU" in filename.upper(): shop_code = filename[0] # Fallback to filename char
		
		# If we have mapped data, prioritize the shop code from inside the file
		if mapped_data and len(mapped_data) > 0:
			shop_code = mapped_data[0].get("store_code", shop_code)
		
		posting_date = summary.get("posting_date")
		if not posting_date:
			date_match = re.search(r"(\d{8})", filename)
			if date_match:
				date_str = date_match.group(1)
				if date_str.startswith('20'):
					posting_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

		# Attach File
		attach_file_to_log(filename, local_path, log)

		if mapped_data:
			# Use new architecture
			enqueue_transactions(mapped_data, log_name=log.name)
			log.status = "Pending"
			log.success_count = 0
			log.error_count = 0
			
			# Accurate metrics for the new architecture
			log.total_records = len(mapped_data)
			log.total_quantity = sum(sum(item.get('qty', 0) for item in txn.get('items', [])) for txn in mapped_data)
			log.total_amount = sum(sum(item.get('amount', 0) for item in txn.get('items', [])) for txn in mapped_data)
		else:
			# Fallback to Frappe Doc Creation for non-transactional files
			result = create_sales_invoices(data, settings, shop_code, posting_date)
			invoices = result.get("invoices", [])
			log.status = "Pending Sync"
			if not invoices and result.get("error_count"):
				log.status = "Failed"
				
			log.success_count = result.get("success_count", 0)
			log.error_count = result.get("error_count", 0)
			log.total_records = len(invoices) + log.error_count
			
			# Update MIS Analytics Data from legacy summary
			log.total_quantity = summary.get("total_qty", 0.0)
			log.total_amount = summary.get("total_amount", 0.0)
			
		log.shop_code = shop_code
		log.file_date = posting_date or getdate()
		
		log.processed_on = now_datetime()
		log.save()
		
		# Archiving is moved to the final Netsuite sync step.
	except Exception as e:
		log.status = "Failed"
		log.logs = frappe.get_traceback()
		log.processed_on = now_datetime()
		log.save()
		frappe.log_error(title=f"Teraoka Sync: File Processing Failed ({filename})", message=frappe.get_traceback())

def attach_file_to_log(filename, local_path, log):
	"""Attaches the downloaded file to the Teraoka File Log record."""
	try:
		from frappe.utils.file_manager import save_file
		with open(local_path, "rb") as f:
			file_content = f.read()
			
		file_doc = save_file(
			filename,
			file_content,
			log.doctype,
			log.name,
			is_private=1
		)
		log.attached_file = file_doc.file_url
	except Exception as e:
		frappe.log_error(title="Teraoka Sync: Attachment Failed", message=frappe.get_traceback())
