import os
import frappe
from frappe import _
from frappe.utils import now_datetime, getdate
from .ftp import list_files, download_file, archive_file
from .parser import parse_csv
from .invoice import create_sales_invoices

@frappe.whitelist()
def sync_teraoka_files():
	"""Main entry point for syncing Teraoka POS files."""
	settings = frappe.get_single("Teraoka Settings")
	if not settings.enabled:
		return
	
	try:
		files = list_files(settings)
		frappe.log_error(f"Files detected on server: {files}", "Teraoka Integration Debug")
		
		if not files:
			frappe.log_error("No files found in remote path", "Teraoka Integration")
			return
			
		for filename in files:
			# Skip hidden files
			if filename.startswith("."):
				continue
				
			# Process .csv files OR the specific 'test_data' file OR any file if we want to be flexible
			if filename.endswith(".csv") or filename == "test_data":
				# Try to get existing log or create new one
				log_name = frappe.db.get_value("Teraoka File Log", 
					{"filename": filename, "processed_on": [">=", getdate()]}, "name")
				
				if log_name:
					log = frappe.get_doc("Teraoka File Log", log_name)
					if log.status == "Success":
						continue
				else:
					log = frappe.new_doc("Teraoka File Log")
					log.filename = filename
					log.status = "Pending"
					log.insert()
				
				# Process File
				process_file(settings, filename, log)
			else:
				frappe.log_error(f"Skipping file {filename}: Not a .csv file", "Teraoka Integration")
				
	except Exception as e:
		title = "Teraoka Sync Failed"
		message = f"Error during sync: {str(e)}"
		frappe.log_error(message, title)

def process_file(settings, filename, log):
	"""Processes a single file."""
	local_path = os.path.join(frappe.get_site_path("private", "files"), filename)
	
	try:
		# Download
		download_file(settings, filename, local_path)
		
		# Parse
		data = parse_csv(local_path)
		
		# Extract shop code from filename (e.g., SHOP01_POS_20260330.csv)
		# Assuming standard prefix or splitting by underscores
		shop_code = filename.split("_")[0]
		
		# Create Invoices
		result = create_sales_invoices(data, settings, shop_code)
		invoices = result.get("invoices", [])
		
		# Attach File
		attach_file_to_log(filename, local_path, log)
		
		# Update Log
		log.status = "Success" if (invoices and not result.get("error_count")) else "Partial Success"
		if not invoices and result.get("error_count"):
			log.status = "Failed"
			
		log.success_count = result.get("success_count", 0)
		log.error_count = result.get("error_count", 0)
		log.processed_on = now_datetime()
		log.save()
		
		# Archive if success
		if log.status == "Success" and settings.archive_processed_files:
			archive_file(settings, filename)
			
	except Exception as e:
		log.status = "Failed"
		log.error_count = 1 # Mark at least one error if it crashed
		log.logs = str(e)
		log.processed_on = now_datetime()
		log.save()
		frappe.log_error(f"File Processing Failed: {filename} - {str(e)}", "Teraoka Integration")
	finally:
		# Optionally keep or delete the file
		pass

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
		frappe.log_error(f"Failed to attach file {filename}: {str(e)}", "Teraoka Integration")
