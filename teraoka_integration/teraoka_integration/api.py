import frappe
from frappe import _
from .ftp import list_files

@frappe.whitelist()
def test_connection(settings):
	"""Tests the SFTP/FTP connection."""
	if isinstance(settings, str):
		settings = frappe.get_doc("Teraoka Settings")
	
	try:
		files = list_files(settings)
		return "OK"
	except Exception as e:
		frappe.throw(_("Connection failed: {0}").format(str(e)))
