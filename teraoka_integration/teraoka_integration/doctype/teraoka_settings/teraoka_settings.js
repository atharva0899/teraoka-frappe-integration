frappe.ui.form.on('Teraoka Settings', {
	refresh: function(frm) {
		frm.add_custom_button(__('Manual Sync'), function() {
			frappe.confirm(__('Are you sure you want to trigger a manual sync now?'), function() {
				frappe.show_alert({message: __('Sync started...'), indicator: 'blue'});
				frappe.call({
					method: "teraoka_integration.teraoka_integration.services.process.sync_teraoka_files",
					callback: function(r) {
						frappe.msgprint({
							title: __('Sync Triggered'),
							message: __('The sync job has been queued in the background. Please monitor the File Logs.'),
							indicator: 'green'
						});
					}
				});
			});
		}).addClass('btn-primary');
	},
	check_connection: function(frm) {
		frm.set_df_property('check_connection', 'label', __('Testing...'));
		
		frappe.call({
			method: "teraoka_integration.teraoka_integration.services.api.test_connection",
			args: {
				settings: frm.doc
			},
			callback: function(r) {
				frm.set_df_property('check_connection', 'label', __('Test Connection'));
				if (r.message === "OK") {
					frappe.msgprint({
						title: __('Connection Success'),
						indicator: 'green',
						message: __('Successfully connected to POS server.')
					});
				}
			},
			error: function() {
				frm.set_df_property('check_connection', 'label', __('Test Connection'));
			}
		});
	}
});
