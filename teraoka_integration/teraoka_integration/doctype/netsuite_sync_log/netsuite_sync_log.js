frappe.ui.form.on('NetSuite Sync Log', {
	refresh(frm) {
		// Make form read-only to protect audit sync trail logs
		frm.disable_form();

		if (frm.doc.status === 'Failed') {
			frm.add_custom_button(__('Retry Sync'), function() {
				frappe.call({
					method: 'teraoka_integration.teraoka_integration.doctype.netsuite_sync_log.netsuite_sync_log.retry_sync',
					args: {
						log_name: frm.doc.name
					},
					freeze: true,
					freeze_message: __('Retrying Sync...'),
					callback: function(r) {
						if (r.message === "Success") {
							frm.reload_doc();
						}
					}
				});
			}).addClass('btn-primary');
		}
	}
});
