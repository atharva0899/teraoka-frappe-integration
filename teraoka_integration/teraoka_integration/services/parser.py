import csv
import os
import frappe
from frappe import _

def clean_float(val):
	"""Robust numeric cleaner for POS data."""
	if val is None: return 0.0
	s_val = str(val).strip()
	if not s_val: return 0.0
	
	# Strip currency symbols and common POS artifacts
	cleaned = "".join(c for c in s_val if c.isdigit() or c in ".-")
	
	try:
		return float(cleaned) if cleaned else 0.0
	except ValueError:
		import re
		match = re.search(r"[-+]?\d*\.?\d+", s_val)
		if match:
			try:
				return float(match.group())
			except:
				return 0.0
		return 0.0

def parse_csv(file_path):
	"""
	Parses Teraoka CSV and aggregates data by Item Code.
	Supports both standard CSV with headers and Raw GYOUMU positional files.
	"""
	aggregated_data = {}
	file_summary = {
		'total_qty': 0.0,
		'total_amount': 0.0,
		'posting_date': None
	}
	
	is_gyoumu = "GYOUMU" in os.path.basename(file_path).upper()
	encoding = 'cp932' if is_gyoumu else 'utf-8-sig'
	
	with open(file_path, mode='r', encoding=encoding, errors='replace') as f:
		# Inspect first line to decide parser mode
		first_line = f.readline()
		f.seek(0)
		
		# If it starts with I3 or TL/IL structure and has no headers, use positional
		if first_line.startswith("I3,") or first_line.startswith("TL,") or is_gyoumu:
			reader = csv.reader(f)
			for row in reader:
				if not row or len(row) < 5: continue
				
				item_code = None
				qty = 0.0
				amount = 0.0
				
				# I3 Structure (Standard Teraoka Sales)
				if row[0] == "I3" and len(row) >= 23:
					item_code = row[16].strip()
					qty = clean_float(row[20])
					amount = clean_float(row[22])
					if not file_summary['posting_date'] and len(row[10]) == 8:
						ds = row[10]
						file_summary['posting_date'] = f"{ds[:4]}-{ds[4:6]}-{ds[6:]}"
						
				# IL Structure (Item Line in Transaction-based files)
				elif row[0] == "IL" and len(row) >= 10:
					item_code = row[4].strip()
					qty = clean_float(row[5])
					amount = clean_float(row[7])
					
				if not item_code: continue

				if item_code not in aggregated_data:
					aggregated_data[item_code] = {'qty': 0.0, 'amount': 0.0}
				
				aggregated_data[item_code]['qty'] += qty
				aggregated_data[item_code]['amount'] += amount
				
				file_summary['total_qty'] += qty
				file_summary['total_amount'] += amount
		else:
			# Standard DictReader for files with headers
			reader = csv.DictReader(f)
			for row in reader:
				# Normalize keys to uppercase and strip
				row = {k.strip().upper(): v for k, v in row.items() if k is not None}
				
				item_code = row.get('ITEM_CODE') or row.get('ITEM CODE') or row.get('JAN_CODE') or row.get('JAN CODE')
				
				if not item_code:
					continue
					
				qty_val = row.get('QTY') or row.get('QUANTITY') or row.get('QTY_SOLD') or 0
				price_val = row.get('PRICE') or row.get('UNIT_PRICE') or 0
				amount_val = row.get('AMOUNT') or row.get('TOTAL') or row.get('TOTAL_AMOUNT') or 0
				
				qty = clean_float(qty_val)
				price = clean_float(price_val)
				amount = clean_float(amount_val)
				
				if amount == 0 and qty != 0 and price != 0:
					amount = qty * price
				elif qty == 0 and price != 0 and amount != 0:
					qty = amount / price
					
				if item_code not in aggregated_data:
					aggregated_data[item_code] = {'qty': 0.0, 'amount': 0.0}
				
				aggregated_data[item_code]['qty'] += qty
				aggregated_data[item_code]['amount'] += amount
				
				file_summary['total_qty'] += qty
				file_summary['total_amount'] += amount

	# Compute weighted average rates
	for item_code in aggregated_data:
		data = aggregated_data[item_code]
		if data['qty'] != 0:
			# Spec: "total value of sale is divided by quantity sold to set rate"
			data['rate'] = data['amount'] / data['qty']
		else:
			data['rate'] = 0.0
			
	return {
		"items": aggregated_data,
		"summary": file_summary
	}

def parse_raw_lines(file_path):
	"""
	Parses the file and returns a list of raw rows (as lists or dicts) for the Splitter.
	"""
	raw_lines = []
	is_gyoumu = "GYOUMU" in os.path.basename(file_path).upper()
	encoding = 'cp932' if is_gyoumu else 'utf-8-sig'
	
	with open(file_path, mode='r', encoding=encoding, errors='replace') as f:
		reader = csv.reader(f)
		for row in reader:
			if row:
				raw_lines.append(row)
	return raw_lines

