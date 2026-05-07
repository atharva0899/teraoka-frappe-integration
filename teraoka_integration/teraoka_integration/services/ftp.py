import os
import ftplib
import paramiko
import frappe
from frappe import _

class TeraokaConnector:
	"""Context manager for FTP/SFTP connections."""
	def __init__(self, settings):
		self.settings = settings
		self.conn = None
		self.transport = None # For SFTP

	def __enter__(self):
		password = self.settings.get_password("password")
		
		if self.settings.is_sftp:
			self.transport = paramiko.Transport((self.settings.host, int(self.settings.port or 22)))
			self.transport.connect(username=self.settings.username, password=password)
			self.conn = paramiko.SFTPClient.from_transport(self.transport)
		else:
			self.conn = ftplib.FTP()
			self.conn.connect(self.settings.host, int(self.settings.port or 21))
			self.conn.login(self.settings.username, password)
		
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		if self.conn:
			self.conn.close()
		if self.transport:
			self.transport.close()

def list_files(settings, conn_obj=None):
	"""Lists files in the remote directory."""
	if conn_obj:
		return _list_files(settings, conn_obj.conn)
	
	with TeraokaConnector(settings) as t:
		return _list_files(settings, t.conn)

def _list_files(settings, conn):
	if settings.is_sftp:
		return conn.listdir(settings.remote_path)
	else:
		return conn.nlst(settings.remote_path)

def download_file(settings, remote_filename, local_path, conn_obj=None):
	"""Downloads a file from the server."""
	if conn_obj:
		return _download_file(settings, remote_filename, local_path, conn_obj.conn)
	
	with TeraokaConnector(settings) as t:
		return _download_file(settings, remote_filename, local_path, t.conn)

def _download_file(settings, remote_filename, local_path, conn):
	remote_full_path = os.path.join(settings.remote_path, remote_filename)
	if settings.is_sftp:
		conn.get(remote_full_path, local_path)
	else:
		with open(local_path, 'wb') as f:
			conn.retrbinary(f'RETR {remote_full_path}', f.write)

def archive_file(settings, filename, conn_obj=None):
	"""Moves the processed file to the archive directory."""
	if not settings.archive_processed_files or not settings.archive_path:
		return
		
	if conn_obj:
		return _archive_file(settings, filename, conn_obj.conn)
	
	with TeraokaConnector(settings) as t:
		return _archive_file(settings, filename, t.conn)

def _archive_file(settings, filename, conn):
	filename = os.path.basename(filename)
	old_path = os.path.join(settings.remote_path, filename)
	new_path = os.path.join(settings.archive_path, filename)
	
	# Simple rename (works for both FTP and SFTP objects)
	conn.rename(old_path, new_path)

