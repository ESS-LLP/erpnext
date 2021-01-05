# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import time_diff_in_seconds, getdate, formatdate

class PractitionerAvailability(Document):
	def validate(self):
		self.validate_repeat_on()
		if self.present == 1:
			validate_duration(self)
		else:
			validate_existing_appointment(self)
		validate_date(self)
		self.to_date = self.from_date
		validate_overlap(self)
		validate_service_unit_capacity(self)

	def validate_repeat_on(self):
		if self.repeat_on == 'Every Day':
			have_atleast_one_weekday = False
			weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
			for weeday in weekdays:
				if self.get(weeday) == 1:
					have_atleast_one_weekday = True
			if not have_atleast_one_weekday:
				frappe.throw("Please select atleast one day")

def validate_duration(doc):
	if not doc.duration or doc.duration <= 0:
		frappe.throw(_("Duration must be geater than zero"))
	else:
		# time diff in minutes = in seconds / 60
		total_time_diff = time_diff_in_seconds(doc.to_time, doc.from_time)/60
		if total_time_diff <= 0:
			frappe.throw(_("From Time should not be greater than or equal to To Time"))
		if total_time_diff < doc.duration:
			frappe.throw(_("Duration between from time and to time must be greater than or equal to duration given"))
		elif total_time_diff % doc.duration != 0:
			frappe.throw(_("Duration between from time and to time must be multiple of duration given"))
def validate_existing_appointment(doc):
	appointment_query = """
		select
			name
		from
			`tabPatient Appointment`
		where
			 practitioner = %(practitioner)s and docstatus < 2 and status != 'Cancelled' and appointment_date = %(from_date)s and (appointment_time >= %(from_time)s and appointment_time < %(to_time)s)
		"""
	appointments = frappe.db.sql(appointment_query.format(doc.doctype),{
			'practitioner': doc.get('practitioner'),
			'from_date': doc.from_date,
			'from_time': doc.from_time,
			'to_time': doc.to_time,
		}, as_dict = 1)
	if appointments:
		frappe.throw(_("Cannot create event!  There are booked appointments at the time, cancel them and proceed."))
def validate_date(doc):
	if doc.repeat_this_event == 1 and doc.repeat_till and getdate(doc.from_date) > getdate(doc.repeat_till):
		frappe.throw(_("Practitioner Event Repeat Till must be after From Date"))

def validate_overlap(doc):
	validate_event_overlap(doc)

def validate_service_unit_capacity(doc):
	if doc.service_unit:
		service_unit_capacity= frappe.get_value('Healthcare Service Unit', doc.service_unit, 'total_service_unit_capacity')
		if doc.total_service_unit_capacity and service_unit_capacity and (int(doc.total_service_unit_capacity)>int(service_unit_capacity)):
			frappe.throw(_("Not Allowed - Maximum Capacity {0}").format(service_unit_capacity))


def validate_event_overlap(doc):
	query = """
		select
			name, from_date, from_time, to_time, service_unit
		from
			`tabPractitioner Availability`
		where
			name != %(name)s and present = %(present)s
			and practitioner = %(practitioner)s and docstatus < 2 and
			(
				(
					repeat_this_event = 1
					and
					(
						(from_date between %(from_date)s and %(repeat_till)s)
						or
						(ifnull(repeat_till, "3000-01-01") between %(from_date)s and %(repeat_till)s)
						or
						(from_date < %(from_date)s and ifnull(repeat_till, "3000-01-01") > %(repeat_till)s)
					)
					and
					(
						(
							repeat_on = 'Every Day'
							and
							(
								monday=%(monday)s or tuesday=%(tuesday)s or wednesday=%(wednesday)s or thursday=%(thursday)s
								or
								friday=%(friday)s or saturday=%(saturday)s or sunday=%(sunday)s
							)
						)
						or
						(
							repeat_on = 'Every Month'
							and
							(
								month(%(from_date)s)=month(from_date)
							)
						)
					)
				)
				or
				(
					repeat_this_event != 1
					and
					(
						(%(from_date)s between from_date and to_date)
						or
						(%(to_date)s between from_date and to_date)
						or
						(%(from_date)s < from_date and %(to_date)s > to_date)
					)
				)
			)
			and
			(
				(from_time >= %(from_time)s and from_time < %(to_time)s)
				or
				(to_time > %(from_time)s and to_time <= %(to_time)s)
				or
				(from_time between %(from_time)s and %(to_time)s) and (to_time between %(from_time)s and %(to_time)s)
				or
				(from_time < %(from_time)s and to_time > %(to_time)s)
			)
		"""

	if not doc.name:
		# hack! if name is null, it could cause problems with !=
		doc.name = "New "+doc.doctype

	overlap_doc = frappe.db.sql(query.format(doc.doctype),{
			'practitioner': doc.get('practitioner'),
			'from_date': doc.from_date,
			'to_date':doc.to_date,
			'from_time': doc.from_time,
			'repeat_till': doc.repeat_till or '3000-01-01',
			'to_time': doc.to_time,
			'name': doc.name,
			'present': doc.present,
			'monday': 1 if doc.monday == 1 else 2,
			'tuesday': 1 if doc.tuesday == 1 else 2,
			'wednesday': 1 if doc.wednesday == 1 else 2,
			'thursday': 1 if doc.thursday == 1 else 2,
			'friday': 1 if doc.friday == 1 else 2,
			'saturday': 1 if doc.saturday == 1 else 2,
			'sunday': 1 if doc.sunday == 1 else 2
		}, as_dict = 1)

	if overlap_doc:
		if doc.service_unit:
			for overlap in overlap_doc:
				if doc.service_unit == overlap.service_unit:
					throw_overlap_error(doc, doc.practitioner, overlap.name, overlap.from_date,
					 overlap.from_time, overlap.to_time)
		else:
			throw_overlap_error(doc, doc.practitioner, overlap_doc[0].name, overlap_doc[0].from_date,
			 overlap_doc[0].from_time, overlap_doc[0].to_time)

def throw_overlap_error(doc, exists_for, overlap_doc, from_date, from_time, to_time):
	msg = _('A {0} exists on {1} with time {2} to {3} (').format(doc.doctype,
		formatdate(from_date), from_time, to_time) \
		+ """ <b><a href="#Form/{0}/{1}">{1}</a></b>""".format(doc.doctype, overlap_doc) \
		+ _(") for {0}").format(exists_for)
	frappe.throw(msg)
