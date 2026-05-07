import frappe
from teraoka_integration.teraoka_integration.ftp import TeraokaConnector, list_files, download_file
import os
import csv

def run():
    settings = frappe.get_single("Teraoka Settings")
    
    try:
        with TeraokaConnector(settings) as tconn:
            files = list_files(settings, conn_obj=tconn)
            print("Files on SFTP:", files)
            
            target_file = None
            for f in files:
                if "GYOUMU" in f.upper() and not f.startswith("."):
                    target_file = f
                    break
                    
            if not target_file:
                print("No GYOUMU file found on SFTP.")
                return
                
            print(f"Downloading {target_file}...")
            local_path = os.path.join(frappe.get_site_path("private", "files"), target_file)
            download_file(settings, target_file, local_path, conn_obj=tconn)
            print(f"Downloaded to {local_path}")
            
            print("Analyzing file structure...")
            with open(local_path, 'r', encoding='cp932', errors='replace') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row and row[0] in ["IL", "I3"]:
                        print(f"\n--- Found Item Line ({row[0]}) ---")
                        for idx, val in enumerate(row):
                            if val.strip():
                                print(f"Index [{idx}]: {val.strip()}")
                        break
    except Exception as e:
        print(f"Failed to connect to SFTP or process file: {e}")
