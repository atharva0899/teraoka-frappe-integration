app_name = "teraoka_integration"
app_title = "Teraoka Integration"
app_publisher = "Ambibuzz Technologies LLP"
app_description = "Consolidated POS Data Integration for Teraoka Machines. Automates SFTP file ingestion, daily aggregation, and ERPNext data synchronization."
app_email = "atharva.joshi@ambibuzz.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "teraoka_integration",
# 		"logo": "/assets/teraoka_integration/logo.png",
# 		"title": "Teraoka Integration",
# 		"route": "/teraoka_integration",
# 		"has_permission": "teraoka_integration.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include_js = "/assets/teraoka_integration/js/teraoka_integration.js"
# include_css = "/assets/teraoka_integration/css/teraoka_integration.css"

# include_js = "teraoka_integration.app"
# include_css = "teraoka_integration.app"

# include_js = "teraoka_integration.web"
# include_css = "teraoka_integration.web"

# before_install = "teraoka_integration.install.before_install"
# after_install = "teraoka_integration.install.after_install"

# Integration Cleanup
# -------------------
# scheduler_events and background_jobs can be used for cleanup tasks
# after_migrate = "teraoka_integration.tasks.cleanup"

# Scheduled Jobs
# ---------------

scheduler_events = {
	"hourly": [
		"teraoka_integration.teraoka_integration.services.process.sync_teraoka_files",
		"teraoka_integration.teraoka_integration.services.netsuite.send_to_netsuite",
		"teraoka_integration.teraoka_integration.services.netsuite.retry_failed_netsuite_syncs"
	]
}

# Testing
# -------

# before_tests = "teraoka_integration.install.before_tests"

# Overriding Methods
# ------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "teraoka_integration.event.get_events"
# }
#
# each method should be in the format 'link_to_method'
#
# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# hook_events = {
# 	"Sales Invoice": {
# 		"after_insert": "teraoka_integration.invoice.after_insert"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"teraoka_integration.tasks.all"
# 	],
# 	"daily": [
# 		"teraoka_integration.tasks.daily"
# 	],
# 	"hourly": [
# 		"teraoka_integration.tasks.hourly"
# 	],
# 	"weekly": [
# 		"teraoka_integration.tasks.weekly"
# 	],
# 	"monthly": [
# 		"teraoka_integration.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "teraoka_integration.install.before_tests"

# Overriding Methods
# ------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "teraoka_integration.event.get_events"
# }
#
# each method should be in the format 'link_to_method'
#
# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# hook_events = {
# 	"DocType": {
# 		"after_insert": "teraoka_integration.event.after_insert",
# 		"on_update": "teraoka_integration.event.on_update",
# 		"on_cancel": "teraoka_integration.event.on_cancel",
# 		"on_trash": "teraoka_integration.event.on_trash"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"teraoka_integration.tasks.all"
# 	],
# 	"daily": [
# 		"teraoka_integration.tasks.daily"
# 	],
# 	"hourly": [
# 		"teraoka_integration.tasks.hourly"
# 	],
# 	"weekly": [
# 		"teraoka_integration.tasks.weekly"
# 	],
# 	"monthly": [
# 		"teraoka_integration.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "teraoka_integration.install.before_tests"

# Overriding Methods
# ------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "teraoka_integration.event.get_events"
# }
#
# each method should be in the format 'link_to_method'
#
# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# hook_events = {
# 	"DocType": {
# 		"after_insert": "teraoka_integration.event.after_insert",
# 		"on_update": "teraoka_integration.event.on_update",
# 		"on_cancel": "teraoka_integration.event.on_cancel",
# 		"on_trash": "teraoka_integration.event.on_trash"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"teraoka_integration.tasks.all"
# 	],
# 	"daily": [
# 		"teraoka_integration.tasks.daily"
# 	],
# 	"hourly": [
# 		"teraoka_integration.tasks.hourly"
# 	],
# 	"weekly": [
# 		"teraoka_integration.tasks.weekly"
# 	],
# 	"monthly": [
# 		"teraoka_integration.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "teraoka_integration.install.before_tests"

# Overriding Methods
# ------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "teraoka_integration.event.get_events"
# }
#
# each method should be in the format 'link_to_method'
#
# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# hook_events = {
# 	"DocType": {
# 		"after_insert": "teraoka_integration.event.after_insert",
# 		"on_update": "teraoka_integration.event.on_update",
# 		"on_cancel": "teraoka_integration.event.on_cancel",
# 		"on_trash": "teraoka_integration.event.on_trash"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"teraoka_integration.tasks.all"
# 	],
# 	"daily": [
# 		"teraoka_integration.tasks.daily"
# 	],
# 	"hourly": [
# 		"teraoka_integration.tasks.hourly"
# 	],
# 	"weekly": [
# 		"teraoka_integration.tasks.weekly"
# 	],
# 	"monthly": [
# 		"teraoka_integration.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "teraoka_integration.install.before_tests"

# Overriding Methods
# ------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "teraoka_integration.event.get_events"
# }
#
# each method should be in the format 'link_to_method'
#
# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# hook_events = {
# 	"DocType": {
# 		"after_insert": "teraoka_integration.event.after_insert",
# 		"on_update": "teraoka_integration.event.on_update",
# 		"on_cancel": "teraoka_integration.event.on_cancel",
# 		"on_trash": "teraoka_integration.event.on_trash"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"teraoka_integration.tasks.all"
# 	],
# 	"daily": [
# 		"teraoka_integration.tasks.daily"
# 	],
# 	"hourly": [
# 		"teraoka_integration.tasks.hourly"
# 	],
# 	"weekly": [
# 		"teraoka_integration.tasks.weekly"
# 	],
# 	"monthly": [
# 		"teraoka_integration.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "teraoka_integration.install.before_tests"

# Overriding Methods
# ------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "teraoka_integration.event.get_events"
# }
#
# each method should be in the format 'link_to_method'
#
# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# hook_events = {
# 	"DocType": {
# 		"after_insert": "teraoka_integration.event.after_insert",
# 		"on_update": "teraoka_integration.event.on_update",
# 		"on_cancel": "teraoka_integration.event.on_cancel",
# 		"on_trash": "teraoka_integration.event.on_trash"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"teraoka_integration.tasks.all"
# 	],
# 	"daily": [
# 		"teraoka_integration.tasks.daily"
# 	],
# 	"hourly": [
# 		"teraoka_integration.tasks.hourly"
# 	],
# 	"weekly": [
# 		"teraoka_integration.tasks.weekly"
# 	],
# 	"monthly": [
# 		"teraoka_integration.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "teraoka_integration.install.before_tests"

# Overriding Methods
# ------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "teraoka_integration.event.get_events"
# }
#
# each method should be in the format 'link_to_method'
#
# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# hook_events = {
# 	"DocType": {
# 		"after_insert": "teraoka_integration.event.after_insert",
# 		"on_update": "teraoka_integration.event.on_update",
# 		"on_cancel": "teraoka_integration.event.on_cancel",
# 		"on_trash": "teraoka_integration.event.on_trash"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"teraoka_integration.tasks.all"
# 	],
# 	"daily": [
# 		"teraoka_integration.tasks.daily"
# 	],
# 	"hourly": [
# 		"teraoka_integration.tasks.hourly"
# 	],
# 	"weekly": [
# 		"teraoka_integration.tasks.weekly"
# 	],
# 	"monthly": [
# 		"teraoka_integration.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "teraoka_integration.install.before_tests"

# Overriding Methods
# ------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "teraoka_integration.event.get_events"
# }
#
# each method should be in the format 'link_to_method'
#
# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# hook_events = {
# 	"DocType": {
# 		"after_insert": "teraoka_integration.event.after_insert",
# 		"on_update": "teraoka_integration.event.on_update",
# 		"on_cancel": "teraoka_integration.event.on_cancel",
# 		"on_trash": "teraoka_integration.event.on_trash"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"teraoka_integration.tasks.all"
# 	],
# 	"daily": [
# 		"teraoka_integration.tasks.daily"
# 	],
# 	"hourly": [
# 		"teraoka_integration.tasks.hourly"
# 	],
# 	"weekly": [
# 		"teraoka_integration.tasks.weekly"
# 	],
# 	"monthly": [
# 		"teraoka_integration.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "teraoka_integration.install.before_tests"

# Overriding Methods
# ------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "teraoka_integration.event.get_events"
# }
#
# each method should be in the format 'link_to_method'
#
# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# hook_events = {
# 	"DocType": {
# 		"after_insert": "teraoka_integration.event.after_insert",
# 		"on_update": "teraoka_integration.event.on_update",
# 		"on_cancel": "teraoka_integration.event.on_cancel",
# 		"on_trash": "teraoka_integration.event.on_trash"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"teraoka_integration.tasks.all"
# 	],
# 	"daily": [
# 		"teraoka_integration.tasks.daily"
# 	],
# 	"hourly": [
# 		"teraoka_integration.tasks.hourly"
# 	],
# 	"weekly": [
# 		"teraoka_integration.tasks.weekly"
# 	],
# 	"monthly": [
# 		"teraoka_integration.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "teraoka_integration.install.before_tests"

# Overriding Methods
# ------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "teraoka_integration.event.get_events"
# }
#
# each method should be in the format 'link_to_method'
#
# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# hook_events = {
# 	"DocType": {
# 		"after_insert": "teraoka_integration.event.after_insert",
# 		"on_update": "teraoka_integration.event.on_update",
# 		"on_cancel": "teraoka_integration.event.on_cancel",
# 		"on_trash": "teraoka_integration.event.on_trash"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"teraoka_integration.tasks.all"
# 	],
# 	"daily": [
# 		"teraoka_integration.tasks.daily"
# 	],
# 	"hourly": [
# 		"teraoka_integration.tasks.hourly"
# 	],
# 	"weekly": [
# 		"teraoka_integration.tasks.weekly"
# 	],
# 	"monthly": [
# 		"teraoka_integration.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "teraoka_integration.install.before_tests"

# Overriding Methods
# ------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "teraoka_integration.event.get_events"
# }
#
# each method should be in the format 'link_to_method'
#
# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# hook_events = {
# 	"DocType": {
# 		"after_insert": "teraoka_integration.event.after_insert",
# 		"on_update": "teraoka_integration.event.on_update",
# 		"on_cancel": "teraoka_integration.event.on_cancel",
# 		"on_trash": "teraoka_integration.event.on_trash"
# 	}
# }
