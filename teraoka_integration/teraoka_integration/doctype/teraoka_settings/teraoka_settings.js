frappe.ui.form.on('Teraoka Settings', {
	refresh: function(frm) {
		frm.add_custom_button(__('Sync Now'), function() {
			frappe.call({
				method: "teraoka_integration.teraoka_integration.process.sync_teraoka_files",
				callback: function(r) {
					frappe.msgprint(__('Sync job started in background. Check Teraoka File Log for status.'));
				}
			});
		}).addClass('btn-primary');
	},
	check_connection: function(frm) {
		frappe.call({
			method: "teraoka_integration.teraoka_integration.api.test_connection",
			args: {
				settings: frm.doc
			},
			callback: function(r) {
				if (r.message === "OK") {
					frappe.msgprint({
						title: __('Success'),
						indicator: 'green',
						message: __('Connection Successful!')
					});
				}
			}
		});
	}
});
