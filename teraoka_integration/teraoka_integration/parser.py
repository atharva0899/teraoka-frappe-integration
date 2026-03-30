import csv
import frappe
from frappe import _

def clean_float(val):
	"""Robust numeric cleaner for POS data."""
	if val is None: return 0.0
	s_val = str(val).strip()
	if not s_val: return 0.0
	
	# Strip currency symbols and common POS artifacts
	# Keep only digits, dots, and minus sign
	cleaned = "".join(c for c in s_val if c.isdigit() or c in ".-")
	
	# Handle cases like '5+' by taking the first sequence of numbers
	try:
		return float(cleaned) if cleaned else 0.0
	except ValueError:
		# Fallback: regex to find the first valid number
		import re
		match = re.search(r"[-+]?\d*\.?\d+", s_val)
		if match:
			try:
				return float(match.group())
			except:
				return 0.0
		return 0.0

def parse_csv(file_path):
	"""Parses Teraoka CSV and aggregates data by Item Code."""
	aggregated_data = {}
	
	with open(file_path, mode='r', encoding='utf-8-sig') as f:
		reader = csv.DictReader(f)
		for row in reader:
			row = {k.strip().upper(): v for k, v in row.items() if k is not None}
			
			item_code = row.get('ITEM_CODE') or row.get('ITEM CODE') or row.get('JAN_CODE') or row.get('JAN CODE')
			
			# Extract values
			qty_val = row.get('QTY') or row.get('QUANTITY') or row.get('QTY_SOLD') or row.get('QTY RANGE') or 0
			amount_val = row.get('AMOUNT') or row.get('TOTAL') or row.get('TOTAL_AMOUNT') or row.get('PRICE') or 0
			
			qty = clean_float(qty_val)
			amount = clean_float(amount_val)
			
			if not item_code:
				continue
			
			if item_code not in aggregated_data:
				aggregated_data[item_code] = {'qty': 0.0, 'amount': 0.0}
			
			aggregated_data[item_code]['qty'] += qty
			aggregated_data[item_code]['amount'] += amount

	# Compute rates
	for item_code in aggregated_data:
		data = aggregated_data[item_code]
		if data['qty'] != 0:
			data['rate'] = data['amount'] / data['qty']
		else:
			data['rate'] = 0.0
			
	return aggregated_data
