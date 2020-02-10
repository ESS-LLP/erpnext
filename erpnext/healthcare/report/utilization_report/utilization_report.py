# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import msgprint, _
from frappe.utils import getdate, nowtime, time_diff_in_seconds, datetime, get_time, date_diff, add_days, get_datetime, formatdate
from functools import reduce

def execute(filters=None):
	if not filters: filters = {}

	event_list = get_events(filters)
	columns = get_columns()

	if not event_list:
		msgprint(_("No record found"))
		return columns, event_list

	data = []
	for pract_event in event_list:
		admin_utilzn = pract_event['app_duration_total']*100/float(pract_event["duration_total"])
		actual_utilzn = pract_event['app_closed_duration_total']*100/float(pract_event["duration_total"])
		schedule_leakage = 1-admin_utilzn
		app_leakage = 1-actual_utilzn
		row = [pract_event["practitioner"], pract_event["appointment_type"], pract_event["duration_total"],
		pract_event['app_duration_total'], pract_event["app_closed_duration_total"], '%0.2f'% admin_utilzn,	'%0.2f'% actual_utilzn, '%0.2f'% schedule_leakage,
		'%0.2f'% app_leakage, pract_event['total_invoice_amt']]
		data.append(row)

	return columns, data

def get_columns():
	columns = [
		_("Name") + ":Link/Healthcare Practitioner:200",
		_("Event Type") + ":Data:150",
		_("Events Duration") + ":Data:200",
		_("Appointments Duration") + ":Data:200",
		_("Visits Duration") + ":Data:120",
		_("Admin Utilization") + ":Data:100",
		_("Actual Utilization") + ":Data:120",
		_("Schedule Leakage") + ":Data:120",
		_("Appointments Leakage") + ":Data:120",
		_("Total of Invoices Amount") + ":Data:250"
	]
	return columns

def get_events(filters):
	start = filters.from_date
	end = filters.to_date
	event_query = """
		select
			name, healthcare_practitioner_name, event, appointment_type, from_time, to_time, from_date, to_date, duration, service_unit, repeat_this_event, repeat_on,
			repeat_till, practitioner, appointment_type, color,
			monday, tuesday, wednesday, thursday, friday, saturday, sunday
		from
			`tabPractitioner Event`
		where
			present = 1 and
			(
				(repeat_this_event = 1 and (from_date<=%(end)s and ifnull(repeat_till, "3000-01-01")>=%(start)s))
				or
				(repeat_this_event != 1 and (from_date<=%(end)s and to_date>=%(start)s))
			)
	"""
	present_events = frappe.db.sql(event_query.format(),{"start":getdate(start), "end":getdate(end)}, as_dict=True)
	data = []
	events_list = []
	length_bw_start_end = date_diff(end, start)+1
	practitioner_event_details = {}
	practitioner_event_details_list = []
	t_event_list = []
	event_dur_dict = {}
	filt_data = []
	eve_duration = 0
	for i in range(0, length_bw_start_end):
		add_events = get_events_by_repeat_on(present_events, add_days(start, i))
		if add_events:
			events_list.append(add_events)

	if events_list and len(events_list) > 0:
		for present_event in events_list:
			if len(present_event) > 0:
				for present_event_details in present_event:
					total_time_diff = time_diff_in_seconds(present_event_details.to_time, present_event_details.from_time)/60
					from_time = present_event_details.from_time
					slot_name = present_event_details.event
					from_date = present_event_details.from_date

					to_time = from_time + datetime.timedelta(seconds=present_event_details.duration*60)
					from frappe.utils import get_time
					start = datetime.datetime.combine(present_event_details.from_date, get_time(from_time))
					end = datetime.datetime.combine(present_event_details.from_date, get_time(to_time))
					for x in range(0, int(total_time_diff), present_event_details.duration):
						to_time = from_time + datetime.timedelta(seconds=present_event_details.duration*60)
						from frappe.utils import get_time
						start = datetime.datetime.combine(present_event_details.from_date, get_time(from_time))
						end = datetime.datetime.combine(present_event_details.from_date, get_time(to_time))
						data.append({'end': end, 'color': present_event_details.color if present_event_details.color else '#cef6d1',
							'doctype': 'Practitioner Event', 'title': present_event_details.event +" - "+ present_event_details.healthcare_practitioner_name,
							'duration':present_event_details.duration, 'name': present_event_details.name, 'start': start,
							'allDay': 0, 'practitioner': present_event_details.practitioner,'practitioner_name': present_event_details.healthcare_practitioner_name, 'service_unit': present_event_details.service_unit,
							'appointment_type': present_event_details.appointment_type})
						from_time = to_time

	for event in present_events:
		event['duration_total'] = 0
		for item in data:
			if item['name'] == event.name:
				event['duration_total'] += item['duration']

	app_query = """
		select
			name, practitioner_event, practitioner, duration, status
		from
			`tabPatient Appointment`
		where
			appointment_date>=%(filters_from_date)s and appointment_date<= %(filters_to_date)s
	"""
	appointments = frappe.db.sql(app_query.format(),{"filters_from_date":getdate(filters.from_date), "filters_to_date":getdate(filters.to_date)}, as_dict=True)
	for event in present_events:
		event['app_duration_total'] = 0
		event['app_closed_duration_total'] = 0
		event['total_invoice_amt'] = 0
		for item in appointments:
			if item['practitioner_event'] == event.name:
				event['app_duration_total'] += item['duration']
				if item['status'] == "Closed":
					event['app_closed_duration_total'] += item['duration']
				si_query = """
					select
						reference_dt, reference_dn, amount
					from
						`tabSales Invoice Item`
					where
						reference_dn=%(app_name)s
				"""
				sales_invoice_item = frappe.db.sql(si_query.format(),{"app_name":item['name']}, as_dict=True)
				if sales_invoice_item:
					event['total_invoice_amt'] += sales_invoice_item[0].amount


	return present_events

def get_events_by_repeat_on(events_list, date):
	add_events = []
	# remove_events = []
	weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
	if events_list:
		# print(events_list)
		for event in events_list:
			repeat_till = getdate(event.repeat_till) if event.repeat_till else getdate('3000-01-01')
			if event.repeat_this_event and (repeat_till >= getdate(date) >= getdate(event.from_date)):
				event.from_date = getdate(date)
				if event.repeat_on == "Every Day":
					if event[weekdays[getdate(date).weekday()]]:
						add_events.append(event.copy())
					# remove_events.append(event.copy())

				if event.repeat_on=="Every Week":
					if getdate(event.from_date).weekday() == getdate(date).weekday():
						add_events.append(event.copy())
					# remove_events.append(event.copy())

				if event.repeat_on=="Every Month":
					if getdate(event.from_date).day == getdate(date).day:
						add_events.append(event.copy())
					# remove_events.append(event.copy())

				if event.repeat_on=="Every Year":
					if getdate(event.from_date).strftime("%j") == getdate(date).strftime("%j"):
						add_events.append(event.copy())
					# remove_events.append(event.copy())
			elif event.from_date == getdate(date):
				add_events.append(event.copy())


		# for e in remove_events:
		# 	events_list.remove(e)
		# events_list = events_list + add_events

		# return events_list
		# for add in add_events:
			# print(add.name)
	return add_events if add_events else False
