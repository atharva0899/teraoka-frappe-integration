frappe.ui.form.on('Teraoka File Log', {
	refresh(frm) {
		// Custom indicator in form header
		let color = 'gray';
		let description = '';
		
		if (frm.doc.status === 'Success') {
			color = 'green';
			description = 'Processing completed successfully.';
		} else if (frm.doc.status === 'Failed') {
			color = 'red';
			description = 'Critical error during processing. Check logs for details.';
		} else if (frm.doc.status === 'Partial Success') {
			color = 'orange';
			description = 'Some invoices were created while others failed.';
		} else {
			color = 'yellow';
			description = 'File is in queue for processing.';
		}
		
		frm.dashboard.set_headline_alert(
			`<div class="indicator ${color}">${__(description)}</div>`
		);

		// Button to view linked invoices
		if (frm.doc.status !== 'Pending') {
			frm.add_custom_button(__('View Created Invoices'), function() {
				frappe.set_route('List', 'Sales Invoice', {
					'posting_date': frm.doc.file_date,
					'remarks': ['like', `%${frm.doc.filename}%`]
				});
			});
		}
	}
});

// List view indicators
frappe.listview_settings['Teraoka File Log'] = {
	get_indicator(doc) {
		const colors = {
			'Success': 'green',
			'Failed': 'red',
			'Partial Success': 'orange',
			'Pending': 'yellow'
		};
		return [__(doc.status), colors[doc.status] || 'gray', `status,=,${doc.status}`];
	}
};
