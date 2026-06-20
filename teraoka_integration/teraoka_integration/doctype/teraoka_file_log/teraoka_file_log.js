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
		} else if (frm.doc.status === 'Pending Sync') {
			color = 'blue';
			description = 'Invoices created. Waiting to sync with NetSuite.';
		} else {
			color = 'yellow';
			description = 'File is in queue for processing.';
		}
		
		frm.dashboard.set_headline_alert(
			`<div class="indicator ${color}">${__(description)}</div>`
		);

		if (frm.doc.status === 'Pending Sync' || frm.doc.status === 'Failed' || frm.doc.status === 'Partial Success' || frm.doc.status === 'Syncing') {
			frm.add_custom_button(__('Sync to NetSuite'), () => {
				frappe.call({
					method: 'teraoka_integration.teraoka_integration.services.netsuite.enqueue_sync_log',
					args: {
						log_name: frm.doc.name
					},
					freeze: true,
					freeze_message: __('Enqueuing NetSuite Sync...'),
					callback: function(r) {
						frm.reload_doc();
						frappe.show_alert(__('NetSuite sync has been enqueued. Processing in background...'));
					}
				});
			});
		}
	}
});


