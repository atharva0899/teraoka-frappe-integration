import frappe
from teraoka_integration.teraoka_integration.ftp import TeraokaConnector, list_files, download_file
import os
import csv

def run():
    settings = frappe.get_single("Teraoka Settings")
    
    try:
        with TeraokaConnector(settings) as tconn:
            target_file = "LGYOUMU.001"
            print(f"Downloading {target_file} from SFTP...")
            local_path = os.path.join(frappe.get_site_path("private", "files"), target_file)
            download_file(settings, target_file, local_path, conn_obj=tconn)
            print(f"Downloaded to {local_path}")
            
            print("Analyzing file structure...")
            with open(local_path, 'r', encoding='cp932', errors='replace') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row and row[0] == "IL":
                        print(f"\n--- Found Item Line (IL) ---")
                        for idx, val in enumerate(row):
                            if val.strip():
                                print(f"Index [{idx}]: {val.strip()}")
                        break
    except Exception as e:
        print(f"Error: {e}")
