import os
import ftplib
import paramiko
import frappe
from frappe import _

def get_ftp_connection(settings):
	"""Returns an FTP or SFTP connection based on settings."""
	password = settings.get_password("password") if hasattr(settings, "get_password") else settings.password
	
	if settings.is_sftp:
		ssh = paramiko.SSHClient()
		ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		ssh.connect(
			hostname=settings.host,
			port=settings.port or 22,
			username=settings.username,
			password=password,
			allow_agent=False,
			look_for_keys=False,
			timeout=10
		)
		return ssh.open_sftp()
	else:
		ftp = ftplib.FTP()
		ftp.connect(settings.host, settings.port or 21)
		ftp.login(settings.username, password)
		return ftp

def archive_file(settings, filename):
	"""Moves the processed file to the archive directory on the remote server."""
	if not settings.archive_processed_files or not settings.archive_path:
		return
		
	# Ensure filename is just the basename
	filename = os.path.basename(filename)
	old_path = os.path.join(settings.remote_path, filename)
	new_path = os.path.join(settings.archive_path, filename)
	
	import paramiko
	from ftplib import FTP
	
	if settings.is_sftp:
		transport = paramiko.Transport((settings.host, int(settings.port or 22)))
		transport.connect(username=settings.username, password=settings.get_password("password"))
		sftp = paramiko.SFTPClient.from_transport(transport)
		try:
			# Ensure archive directory exists (simple way: try rename, or mkdir if needed)
			# Actually, paramiko rename might fail if target exists.
			sftp.rename(old_path, new_path)
		finally:
			sftp.close()
			transport.close()
	else:
		ftp = FTP()
		ftp.connect(settings.host, int(settings.port or 21))
		ftp.login(settings.username, settings.get_password("password"))
		try:
			ftp.rename(old_path, new_path)
		finally:
			ftp.quit()

def download_file(settings, remote_filename, local_path):
	"""Downloads a file from the FTP/SFTP server."""
	conn = get_ftp_connection(settings)
	remote_full_path = os.path.join(settings.remote_path, remote_filename)
	
	try:
		if settings.is_sftp:
			conn.get(remote_full_path, local_path)
		else:
			with open(local_path, 'wb') as f:
				conn.retrbinary(f'RETR {remote_full_path}', f.write)
	finally:
		conn.close()

def list_files(settings):
	"""Lists files in the remote directory."""
	conn = get_ftp_connection(settings)
	try:
		if settings.is_sftp:
			return conn.listdir(settings.remote_path)
		else:
			return conn.nlst(settings.remote_path)
	finally:
		conn.close()
