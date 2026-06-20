frappe.listview_settings['Teraoka File Log'] = {
	get_indicator(doc) {
		const colors = {
			'Success': 'green',
			'Failed': 'red',
			'Partial Success': 'orange',
			'Pending Sync': 'blue',
			'Pending': 'yellow'
		};
		return [__(doc.status), colors[doc.status] || 'gray', `status,=,${doc.status}`];
	}
};
