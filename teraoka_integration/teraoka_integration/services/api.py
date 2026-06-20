import frappe
from frappe import _
from .ftp import list_files

@frappe.whitelist()
def test_connection(settings=None):
	"""Tests the SFTP/FTP connection."""
	if not settings:
		settings = frappe.get_doc("Teraoka Settings")
	elif isinstance(settings, str):
		import json
		try:
			settings = json.loads(settings)
		except Exception:
			settings = frappe.get_doc("Teraoka Settings")
			
	if isinstance(settings, dict):
		settings = frappe.get_doc(settings)
	
	try:
		files = list_files(settings)
		return "OK"
	except Exception as e:
		frappe.throw(_("Connection failed: {0}").format(str(e)))

