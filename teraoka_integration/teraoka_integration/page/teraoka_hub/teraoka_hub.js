frappe.pages['teraoka-hub'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Teraoka Integration Hub',
		single_column: true
	});

	// Inject Google Font
	if (!$("link[href*='Inter']").length) {
		$("<link>").attr({
			rel: "stylesheet",
			type: "text/css",
			href: "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
		}).appendTo("head");
	}

	page.set_title_sub('Teraoka Integration Gateway');

	// Add manual refresh button
	page.set_primary_action('Refresh Data', () => {
		const val = page.date_range ? page.date_range.get_value() : null;
		const shop = page.current_shop;
		if (val && val.length === 2) {
			render_dashboard_content(val[0], val[1], shop);
		} else {
			render_dashboard_content();
		}
	}, 'icon-refresh');

	// Add connection diagnostics button
	page.add_inner_button('Run Connectivity Diagnostics', () => {
		run_diagnostics_api();
	});

	// Add manual sync trigger
	page.add_inner_button('Force SFTP Sync', () => {
		trigger_sync_api();
	});

	// Build the persistent structure
	$(page.main).html(`
		<div class="teraoka-dashboard">
			<div class="dashboard-header-flex">
				<div>
					<div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
						<h2 id="hub-main-title">Integration Performance Monitor</h2>
						<div id="shop-filter-badge"></div>
					</div>
					<div class="subtitle" id="dashboard-sync-time">Enterprise Data Synchronization Console</div>
				</div>
				<div class="dashboard-filter-box" style="display: flex; align-items: center; gap: 20px; flex-wrap: wrap;">
					<!-- Connectivity Status Indicators -->
					<div id="diagnostics-summary-bar" style="display: flex; gap: 10px;">
						<span class="diagnostic-badge sftp-status unknown" title="SFTP POS Server"><i class="fa fa-server"></i> SFTP: Unknown</span>
						<span class="diagnostic-badge ns-status unknown" title="NetSuite API"><i class="fa fa-cloud"></i> NetSuite: Unknown</span>
					</div>
					<!-- Auto-Refresh Toggle -->
					<div class="auto-refresh-wrapper" style="display: flex; align-items: center; gap: 8px;">
						<label class="switch-container" style="position: relative; display: inline-block; width: 34px; height: 20px; margin-bottom: 0;">
							<input type="checkbox" id="auto-refresh-checkbox" style="opacity: 0; width: 0; height: 0;">
							<span class="slider-switch" style="position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #cbd5e1; transition: .3s; border-radius: 20px;"></span>
						</label>
						<span class="refresh-label" style="font-size: 12px; color: #64748b; font-weight: 500;">Auto-Refresh (30s)</span>
					</div>
					<div id="teraoka-date-range-container" style="min-width: 250px;"></div>
				</div>
			</div>
			<div id="dashboard-content-area" style="min-height: 500px;">
				<div style="padding: 150px; text-align: center; color: #8b949e;">
					<h3>Initializing Hub...</h3>
					<p>Assembling operational intelligence...</p>
				</div>
			</div>
		</div>
	`);

	// Initialize the Frappe DateRange Control
	page.date_range = frappe.ui.form.make_control({
		df: {
			fieldtype: 'DateRange',
			label: 'Audit Period',
			fieldname: 'date_range',
			placeholder: 'Select Date Range',
			on_change: function() {
				const val = this.get_value();
				if (val && val.length === 2) {
					render_dashboard_content(val[0], val[1], page.current_shop);
				}
			}
		},
		parent: $(page.main).find('#teraoka-date-range-container'),
		render_input: true
	});

	// Initial Load: Default to Today
	const today = frappe.datetime.get_today();
	page.date_range.set_value([today, today]);
	render_dashboard_content(today, today);

	// Setup Auto-Refresh Interval
	page.auto_refresh_interval = null;
	const $checkbox = $(page.main).find('#auto-refresh-checkbox');
	$checkbox.on('change', function() {
		if (this.checked) {
			page.auto_refresh_interval = setInterval(() => {
				const val = page.date_range ? page.date_range.get_value() : null;
				const shop = page.current_shop;
				if (val && val.length === 2) {
					render_dashboard_content(val[0], val[1], shop, true); // silent refresh
				} else {
					render_dashboard_content(null, null, null, true);
				}
			}, 30000);
		} else {
			if (page.auto_refresh_interval) {
				clearInterval(page.auto_refresh_interval);
				page.auto_refresh_interval = null;
			}
		}
	});

	// Cleanup Auto-Refresh when leaving/destroying frame
	$(wrapper).on('destroy', () => {
		if (page.auto_refresh_interval) {
			clearInterval(page.auto_refresh_interval);
		}
	});

	// Run Diagnostics shortly after page load
	setTimeout(run_diagnostics_api, 800);
}

function trigger_sync_api() {
	frappe.show_alert({message: __('Enqueuing SFTP Sync...'), indicator: 'blue'});
	frappe.call({
		method: 'teraoka_integration.teraoka_integration.page.teraoka_hub.teraoka_hub.trigger_sync',
		callback: function(r) {
			if (r.message && r.message.status === 'Success') {
				frappe.show_alert({message: __('Background sync started successfully.'), indicator: 'green'});
			}
		}
	});
}

function run_diagnostics_api() {
	const $sftp = $('.diagnostic-badge.sftp-status');
	const $ns = $('.diagnostic-badge.ns-status');
	
	$sftp.attr('class', 'diagnostic-badge sftp-status checking').html('<i class="fa fa-spinner fa-spin"></i> SFTP: Testing...');
	$ns.attr('class', 'diagnostic-badge ns-status checking').html('<i class="fa fa-spinner fa-spin"></i> NetSuite: Testing...');
	
	frappe.call({
		method: 'teraoka_integration.teraoka_integration.page.teraoka_hub.teraoka_hub.run_connectivity_diagnostics',
		callback: function(r) {
			if (r.message) {
				const sftp = r.message.sftp;
				const netsuite = r.message.netsuite;
				
				if (sftp.status === 'Success') {
					$sftp.attr('class', 'diagnostic-badge sftp-status success')
						.html('<i class="fa fa-check-circle"></i> SFTP: Connected')
						.attr('title', 'SFTP POS Server: Connection Successful');
				} else {
					$sftp.attr('class', 'diagnostic-badge sftp-status failed')
						.html('<i class="fa fa-times-circle"></i> SFTP: Error')
						.attr('title', `SFTP POS Server Error: ${sftp.message}`);
				}
				
				if (netsuite.status === 'Success') {
					$ns.attr('class', 'diagnostic-badge ns-status success')
						.html('<i class="fa fa-check-circle"></i> NetSuite: Connected')
						.attr('title', 'NetSuite REST API: Connection Successful');
				} else if (netsuite.status === 'Disabled') {
					$ns.attr('class', 'diagnostic-badge ns-status disabled')
						.html('<i class="fa fa-minus-circle"></i> NetSuite: Disabled')
						.attr('title', 'NetSuite integration is disabled in settings');
				} else {
					$ns.attr('class', 'diagnostic-badge ns-status failed')
						.html('<i class="fa fa-times-circle"></i> NetSuite: Error')
						.attr('title', `NetSuite API Error: ${netsuite.message || netsuite.error}`);
				}
			} else {
				$sftp.attr('class', 'diagnostic-badge sftp-status unknown').html('<i class="fa fa-question-circle"></i> SFTP: Unknown');
				$ns.attr('class', 'diagnostic-badge ns-status unknown').html('<i class="fa fa-question-circle"></i> NetSuite: Unknown');
				frappe.show_alert({message: __('Diagnostics failed.'), indicator: 'red'});
			}
		}
	});
}

function render_dashboard_content(from_date, to_date, shop_code, silent = false) {
	const $content = $('#dashboard-content-area');
	if (!$content.length) return;

	if (!silent) {
		$content.css('opacity', '0.5');
	}

	frappe.call({
		method: 'teraoka_integration.teraoka_integration.page.teraoka_hub.teraoka_hub.get_dashboard_data',
		args: { from_date: from_date, to_date: to_date, shop_code: shop_code },
		callback: function(r) {
			$content.css('opacity', '1');
			if (r.message) {
				update_ui(r.message);
			} else {
				if (!silent) {
					$content.html('<div class="alert alert-danger">Failed to load analytics. Please try refreshing.</div>');
				}
			}
		}
	});
}

function update_ui(data) {
	const $content = $('#dashboard-content-area');
	if (!$content.length) return;

	// Update Global Filter State
	const page = frappe.pages['teraoka-hub'].page;
	page.current_shop = data.shop_code;

	try {
		const logs = data.recent_logs || [];
		const p = data.pipeline || {};
		const briefing = data.briefing || [];
		const actions = data.actions || [];
		const growth = parseFloat(data.growth) || 0;
		
		const get_node_class = (status) => {
			if (status === 'success') return 'active success';
			if (status === 'error') return 'active error';
			if (status === 'active') return 'active pulse-active';
			return '';
		};

		// Update Header Title & Filter Badge
		$('#dashboard-sync-time').text(`Enterprise Data Synchronization Console (Last Sync: ${data.last_sync || 'Never'})`);
		if (data.shop_code) {
			$('#shop-filter-badge').html(`
				<span class="active-shop-tag">
					Shop ${data.shop_code} <i class="fa fa-times" onclick="clear_shop_filter()"></i>
				</span>
			`);
		} else {
			$('#shop-filter-badge').empty();
		}

		// SECTION 1: Intelligence Snapshot
		let snapshot_html = `
			<div class="hub-section">
				<div class="section-label">Section 01: Intelligence Snapshot</div>
				<div class="overview-grid">
					<div class="briefing-card">
						<div class="briefing-header"><i class="fa fa-commenting-o"></i> Operational Briefing</div>
						<div class="briefing-body">${briefing.map(line => `<p>${line}</p>`).join('')}</div>
					</div>
					<div class="summary-cards-container">
						<div class="t-card">
							<div class="t-card-header"><span class="t-card-title">Total Sales</span><div class="t-card-icon icon-blue"><i class="fa fa-line-chart"></i></div></div>
							<div class="t-card-value">${data.total_sales || '¥ 0.00'}<span class="growth-badge ${growth >= 0 ? 'positive' : 'negative'}">${growth >= 0 ? '+' : ''}${growth.toFixed(1)}%</span></div>
						</div>
						<div class="t-card highlight">
							<div class="t-card-header"><span class="t-card-title">System Health</span><div class="t-card-icon icon-green"><i class="fa fa-heartbeat"></i></div></div>
							<div class="t-card-value">${data.health || 'Healthy'}<span class="t-badge success">Active</span></div>
						</div>
						<div class="t-card">
							<div class="t-card-header"><span class="t-card-title">Success Rate</span><div class="t-card-icon icon-blue"><i class="fa fa-check-circle"></i></div></div>
							<div class="t-card-value">${data.success_rate || 0}%</div>
						</div>
						<div class="t-card queue-card">
							<div class="t-card-header"><span class="t-card-title">Queue Status</span><div class="t-card-icon icon-orange"><i class="fa fa-tasks"></i></div></div>
							<div class="t-card-value" style="font-size: 15px; flex-direction: column; align-items: flex-start; gap: 4px;">
								<div><span style="font-weight: 700; color: #f59e0b;">${data.processing_count || 0}</span> Processing</div>
								<div style="font-size: 11px; color: #64748b;"><span style="font-weight: 600;">${data.pending_sync_count || 0}</span> Pending NetSuite Sync</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		`;

		// SECTION 2: System Diagnostics
		let diagnostics_html = `
			<div class="hub-section">
				<div class="section-label">Section 02: System Diagnostics</div>
				<div class="pipeline-view">
					<div class="pipeline-track">
						<div class="pipeline-line"></div>
						<div class="pipeline-node ${get_node_class(p.sftp)}" title="Fetch Files"><i class="fa fa-server"></i><span class="node-label">Fetch Files</span></div>
						<div class="pipeline-node ${get_node_class(p.parser)}" title="Parse Data"><i class="fa fa-file-code-o"></i><span class="node-label">Parse Data</span></div>
						<div class="pipeline-node ${get_node_class(p.mapper)}" title="Map Records"><i class="fa fa-exchange"></i><span class="node-label">Map Records</span></div>
						<div class="pipeline-node ${get_node_class(p.invoice)}" title="Create Invoices"><i class="fa fa-file-text-o"></i><span class="node-label">Create Invoices</span></div>
						<div class="pipeline-node ${get_node_class(p.netsuite)}" title="Sync NetSuite"><i class="fa fa-cloud-upload"></i><span class="node-label">Sync NetSuite</span></div>
					</div>
				</div>
			</div>
		`;

		// SECTION 3: Performance Analytics
		let analytics_html = `
			<div class="hub-section">
				<div class="section-label">Section 03: Performance Analytics</div>
				<div class="chart-container">
					<h3>${(data.chart && data.chart.title) ? data.chart.title : 'Sales Velocity Trend'}</h3>
					<div id="sales-trend-chart"></div>
				</div>
			</div>
		`;

		// SECTION 4: Operational Matrix
		let matrix_html = `
			<div class="hub-section">
				<div class="section-label">Section 04: Operational Matrix</div>
				<div class="shop-matrix-section">
					<div class="shop-grid">
						${(data.shop_stats || []).map(shop => `
							<div class="shop-card drill-down ${data.shop_code === shop.shop_code ? 'active' : ''}" onclick="apply_shop_filter('${shop.shop_code}')">
								<div class="shop-header">
									<span class="shop-code">Shop ${shop.shop_code}</span>
									<span class="status-dot ${shop.status === 'Success' ? 'online' : 'warning'}"></span>
								</div>
								<div class="shop-sales">${frappe.format(shop.sales, {fieldtype: 'Currency'})}</div>
								<div class="shop-sync">Last Sync: ${shop.last_sync ? frappe.datetime.global_date_format(shop.last_sync) : 'Never'}</div>
								<div class="drill-hint">Click to inspect <i class="fa fa-search-plus"></i></div>
							</div>
						`).join('')}
					</div>
				</div>
			</div>
		`;

		// SECTION 5: Audit Ledger
		let ledger_html = `
			<div class="hub-section no-border">
				<div class="section-label">Section 05: Audit Ledger</div>
				<div class="recent-activity-section">
					<div class="activity-table-wrapper">
						<table class="activity-table">
							<thead>
								<tr><th>Filename</th><th>Processed</th><th>Success</th><th>Status</th><th>Actions</th></tr>
							</thead>
							<tbody>
								${logs.map(log => `
									<tr>
										<td class="bold">${log.filename || 'Unknown'}</td>
										<td>${log.processed_on ? frappe.datetime.global_date_format(log.processed_on) : 'In Progress'}</td>
										<td>${log.success_count || 0} / ${log.total_records || 0}</td>
										<td><span class="status-badge ${(log.status || 'pending').toLowerCase().replace(/ /g, '-')}">${log.status || 'Pending'}</span></td>
										<td><a href="/app/teraoka-file-log/${log.name}" class="btn-link">View Details</a></td>
									</tr>
								`).join('')}
							</tbody>
						</table>
					</div>
				</div>
			</div>
		`;

		// Critical Action Center
		let action_html = '';
		if (actions.length > 0) {
			action_html = `
				<div class="action-center-section">
					<h3><i class="fa fa-exclamation-triangle"></i> CRITICAL: Actions Required</h3>
					<div class="action-list">
						${actions.map(action => `
							<div class="action-item" id="action-log-${action.log_name}" style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
								<span>${action.message}</span>
								<div style="display: flex; gap: 8px;">
									<button onclick="reprocess_log_file('${action.log_name}')" class="btn btn-default btn-xs btn-retry-action" style="font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 4px;">
										<i class="fa fa-refresh"></i> Retry Reprocessing
									</button>
									<a href="${action.link}" class="btn-action" style="font-size: 11px; padding: 4px 10px; border-radius: 4px;">View Details</a>
								</div>
							</div>
						`).join('')}
					</div>
				</div>
			`;
		}

		$content.html(`
			${action_html}
			${snapshot_html}
			${diagnostics_html}
			${analytics_html}
			${matrix_html}
			${ledger_html}
		`);

		// Render the Chart
		if (data.chart && data.chart.labels && data.chart.labels.length > 0) {
			new frappe.Chart("#sales-trend-chart", {
				data: { labels: data.chart.labels, datasets: [{ name: "Sales", values: data.chart.values }] },
				type: 'line', height: 250, colors: ['#3b82f6'], lineOptions: { regionFill: 1 }
			});
		}

	} catch (e) {
		console.error("Dashboard Render Error:", e);
		$content.html('<div class="alert alert-danger">Rendering Error. Please reload.</div>');
	}
}

window.reprocess_log_file = function(log_name) {
	const $item = $(`#action-log-${log_name}`);
	const $btn = $item.find('.btn-retry-action');
	
	$btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Enqueuing...');
	
	frappe.call({
		method: 'teraoka_integration.teraoka_integration.page.teraoka_hub.teraoka_hub.reprocess_file',
		args: { log_name: log_name },
		callback: function(r) {
			if (r.message && r.message.status === 'Success') {
				frappe.show_alert({message: __('File processing enqueued successfully.'), indicator: 'green'});
				
				// Instantly reload dashboard
				const page = frappe.pages['teraoka-hub'].page;
				const val = page.date_range ? page.date_range.get_value() : null;
				const shop = page.current_shop;
				if (val && val.length === 2) {
					render_dashboard_content(val[0], val[1], shop);
				} else {
					render_dashboard_content();
				}
			} else {
				$btn.prop('disabled', false).html('<i class="fa fa-refresh"></i> Retry Reprocessing');
				frappe.show_alert({message: __('Enqueuing failed.'), indicator: 'red'});
			}
		},
		error: function() {
			$btn.prop('disabled', false).html('<i class="fa fa-refresh"></i> Retry Reprocessing');
		}
	});
};

window.apply_shop_filter = function(shop_code) {
	const page = frappe.pages['teraoka-hub'].page;
	const val = page.date_range.get_value();
	render_dashboard_content(val[0], val[1], shop_code);
}

window.clear_shop_filter = function() {
	const page = frappe.pages['teraoka-hub'].page;
	const val = page.date_range.get_value();
	render_dashboard_content(val[0], val[1], null);
}