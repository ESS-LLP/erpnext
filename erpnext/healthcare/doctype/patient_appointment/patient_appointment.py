# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS LLP and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import json
from frappe.utils import getdate, get_time, add_days, time_diff_in_seconds
from frappe.model.mapper import get_mapped_doc
from frappe import _
import datetime
from frappe.core.doctype.sms_settings.sms_settings import send_sms
from erpnext.hr.doctype.employee.employee import is_holiday
from erpnext.healthcare.doctype.healthcare_settings.healthcare_settings import get_receivable_account, get_income_account
from erpnext.healthcare.utils import check_fee_validity, get_service_item_and_practitioner_charge, manage_fee_validity

class Maximumcapacityerror(frappe.ValidationError): pass
class Overlappingerror(frappe.ValidationError): pass

class PatientAppointment(Document):
	def validate(self):
		self.validate_overlaps()
		self.set_appointment_datetime()
		self.validate_customer_created()
		self.set_status()
		self.set_title()

	def after_insert(self):
		self.update_prescription_details()
		invoice_appointment(self)
		self.update_fee_validity()
		send_confirmation_msg(self)

	def set_title(self):
		self.title = _('{0} with {1}').format(self.patient_name or self.patient,
			self.practitioner_name or self.practitioner)

	def set_status(self):
		today = getdate()
		appointment_date = getdate(self.appointment_date)

		# If appointment is created for today set status as Open else Scheduled
		if appointment_date == today:
			self.status = 'Open'
		elif appointment_date > today:
			self.status = 'Scheduled'

	def validate_overlaps(self):
		end_time = datetime.datetime.combine(getdate(self.appointment_date), get_time(self.appointment_time)) \
			 + datetime.timedelta(minutes=flt(self.duration))

		query = """
		select
			name, practitioner, patient, appointment_time, duration
		from
			`tabPatient Appointment`
		where
			appointment_date=%(appointment_date)s and name!=%(name)s and status NOT IN ("Closed", "Cancelled")
			and (practitioner=%(practitioner)s or patient=%(patient)s) and
			((appointment_time<%(appointment_time)s and appointment_time + INTERVAL duration MINUTE>%(appointment_time)s) or
			(appointment_time>%(appointment_time)s and appointment_time<%(end_time)s) or
			(appointment_time=%(appointment_time)s))
		"""

		# service unit overlap
		if self.service_unit:
			query +=""" and service_unit=%(service_unit)s"""
			overlaps = frappe.db.sql(query.format(),{'appointment_date':self.appointment_date, 'name':self.name, 'practitioner':self.practitioner,
			'patient':self.patient, 'appointment_time':self.appointment_time,  'end_time':end_time.time(), 'service_unit':self.service_unit})
			allow_overlap = frappe.get_value('Healthcare Service Unit', self.service_unit, 'overlap_appointments')
			if allow_overlap:
				if self.practitioner_availability:
					service_unit_capacity= frappe.get_value('Practitioner Availability', self.practitioner_availability, 'total_service_unit_capacity')
				else:
					service_unit_capacity= frappe.get_value('Healthcare Service Unit', self.service_unit, 'total_service_unit_capacity')

				if service_unit_capacity and  len(overlaps)>=int(service_unit_capacity):
					frappe.throw(_(""" Not Allowed, Maximum capacity reached Service unit {0}""").format(self.service_unit), Maximumcapacityerror)
				else:
					 overlaps = False
		else:
			overlaps  = frappe.db.sql(query.format(),{"appointment_date":self.appointment_date, "name":self.name, "practitioner":self.practitioner,
			"patient":self.patient, "appointment_time":self.appointment_time,  "end_time":end_time.time()})

		if overlaps:
			frappe.throw(_("""Appointment overlaps with {0}.<br> {1} has appointment scheduled
			with {2} at {3} having {4} minute(s) duration.""").format(overlaps[0][0], overlaps[0][1], overlaps[0][2], overlaps[0][3], overlaps[0][4]), Overlappingerror)

		if self.service_unit:
			service_unit_company = frappe.db.get_value("Healthcare Service Unit", self.service_unit, "company")
			if service_unit_company and service_unit_company != self.company:
				self.company = service_unit_company

	def set_appointment_datetime(self):
		self.appointment_datetime = "%s %s" % (self.appointment_date, self.appointment_time or "00:00:00")

	def validate_customer_created(self):
		if frappe.db.get_single_value('Healthcare Settings', 'automate_appointment_invoicing'):
			if not frappe.db.get_value('Patient', self.patient, 'customer'):
				msg = _("Please set a Customer linked to the Patient")
				msg +=  " <b><a href='#Form/Patient/{0}'>{0}</a></b>".format(self.patient)
				frappe.throw(msg, title=_('Customer Not Found'))

	def update_prescription_details(self):
		if self.procedure_prescription:
			frappe.db.set_value('Procedure Prescription', self.procedure_prescription, 'appointment_booked', 1)
			if self.procedure_template:
				comments = frappe.db.get_value('Procedure Prescription', self.procedure_prescription, 'comments')
				if comments:
					frappe.db.set_value('Patient Appointment', self.name, 'notes', comments)
		elif self.radiology_procedure_prescription:
			frappe.db.set_value("Radiology Procedure Prescription", self.radiology_procedure_prescription, "appointment_booked", True)

	def update_fee_validity(self):
		fee_validity = manage_fee_validity(self)
		if fee_validity:
			frappe.msgprint(_('{0} has fee validity till {1}').format(self.patient, fee_validity.valid_till))


@frappe.whitelist()
def check_payment_fields_reqd(patient):
	automate_invoicing = frappe.db.get_single_value('Healthcare Settings', 'automate_appointment_invoicing')
	free_follow_ups = frappe.db.get_single_value('Healthcare Settings', 'enable_free_follow_ups')
	if automate_invoicing:
		if free_follow_ups:
			fee_validity = frappe.db.exists('Fee Validity', {'patient': patient, 'status': 'Pending'})
			if fee_validity:
				return {'fee_validity': fee_validity}
			if check_is_new_patient(patient):
				return False
		return True
	return False

def invoice_appointment(appointment_doc):
	automate_invoicing = frappe.db.get_single_value('Healthcare Settings', 'automate_appointment_invoicing')
	appointment_invoiced = frappe.db.get_value('Patient Appointment', appointment_doc.name, 'invoiced')
	enable_free_follow_ups = frappe.db.get_single_value('Healthcare Settings', 'enable_free_follow_ups')
	if enable_free_follow_ups:
		fee_validity = check_fee_validity(appointment_doc)
		if fee_validity and fee_validity.status == 'Completed':
			fee_validity = None
		elif not fee_validity:
			if frappe.db.exists('Fee Validity Reference', {'appointment': appointment_doc.name}):
				return
			if check_is_new_patient(appointment_doc.patient, appointment_doc.name):
				return
	else:
		fee_validity = None

	if automate_invoicing and not appointment_invoiced and not fee_validity:
		sales_invoice = frappe.new_doc('Sales Invoice')
		sales_invoice.patient = appointment_doc.patient
		sales_invoice.customer = frappe.get_value('Patient', appointment_doc.patient, 'customer')
		sales_invoice.appointment = appointment_doc.name
		sales_invoice.due_date = getdate()
		sales_invoice.company = appointment_doc.company
		sales_invoice.debit_to = get_receivable_account(appointment_doc.company)

		item = sales_invoice.append('items', {})
		item = get_appointment_item(appointment_doc, item)

		# Add payments if payment details are supplied else proceed to create invoice as Unpaid
		if appointment_doc.mode_of_payment and appointment_doc.paid_amount:
			sales_invoice.is_pos = 1
			payment = sales_invoice.append('payments', {})
			payment.mode_of_payment = appointment_doc.mode_of_payment
			payment.amount = appointment_doc.paid_amount

		sales_invoice.set_missing_values(for_validate=True)
		sales_invoice.flags.ignore_mandatory = True
		sales_invoice.save(ignore_permissions=True)
		sales_invoice.submit()
		frappe.msgprint(_('Sales Invoice {0} created'.format(sales_invoice.name)), alert=True)
		frappe.db.set_value('Patient Appointment', appointment_doc.name, 'invoiced', 1)
		frappe.db.set_value('Patient Appointment', appointment_doc.name, 'ref_sales_invoice', sales_invoice.name)


def check_is_new_patient(patient, name=None):
	filters = {'patient': patient, 'status': ('!=','Cancelled')}
	if name:
		filters['name'] = ('!=', name)

	has_previous_appointment = frappe.db.exists('Patient Appointment', filters)
	if has_previous_appointment:
		return False
	return True


def get_appointment_item(appointment_doc, item):
	service_item, practitioner_charge = get_service_item_and_practitioner_charge(appointment_doc)
	item.item_code = service_item
	item.description = _('Consulting Charges: {0}').format(appointment_doc.practitioner)
	item.income_account = get_income_account(appointment_doc.practitioner, appointment_doc.company)
	item.cost_center = frappe.get_cached_value('Company', appointment_doc.company, 'cost_center')
	item.rate = practitioner_charge
	item.amount = practitioner_charge
	item.qty = 1
	item.reference_dt = 'Patient Appointment'
	item.reference_dn = appointment_doc.name
	return item


def cancel_appointment(appointment_id):
	appointment = frappe.get_doc('Patient Appointment', appointment_id)
	if appointment.invoiced:
		sales_invoice = check_sales_invoice_exists(appointment)
		if sales_invoice and cancel_sales_invoice(sales_invoice):
			msg = _('Appointment {0} and Sales Invoice {1} cancelled').format(appointment.name, sales_invoice.name)
		else:
			msg = _('Appointment Cancelled. Please review and cancel the invoice {0}').format(sales_invoice.name)
	else:
		fee_validity = manage_fee_validity(appointment)
		msg = _('Appointment Cancelled.')
		if fee_validity:
			msg += _('Fee Validity {0} updated.').format(fee_validity.name)

	frappe.msgprint(msg)


def cancel_sales_invoice(sales_invoice):
	if frappe.db.get_single_value('Healthcare Settings', 'automate_appointment_invoicing'):
		if len(sales_invoice.items) == 1:
			sales_invoice.cancel()
			return True
	return False


def check_sales_invoice_exists(appointment):
	sales_invoice = frappe.db.get_value('Sales Invoice Item', {
		'reference_dt': 'Patient Appointment',
		'reference_dn': appointment.name
	}, 'parent')

	if sales_invoice:
		sales_invoice = frappe.get_doc('Sales Invoice', sales_invoice)
		return sales_invoice
	return False


@frappe.whitelist()
def get_availability_data(date, practitioner):
	"""
	Get availability data of 'practitioner' on 'date'
	:param date: Date to check in schedule
	:param practitioner: Name of the practitioner
	:return: dict containing a list of available slots, list of appointments and time of appointments
	"""

	date = getdate(date)
	weekday = date.strftime('%A')

	practitioner_doc = frappe.get_doc('Healthcare Practitioner', practitioner)

	check_employee_wise_availability(date, practitioner_doc)
	present_events = get_present_event(practitioner, date)

	if practitioner_doc.practitioner_schedules or present_events:
		slot_details = get_available_slots(practitioner_doc, date)
		present_events = get_present_event_slots(present_events, date, practitioner)
	else:
		frappe.throw(_('{0} does not have a Healthcare Practitioner Schedule. Add it in Healthcare Practitioner master').format(
			practitioner), title=_('Practitioner Schedule Not Found'))


	if not slot_details  and not present_events:
		# TODO: return available slots in nearby dates
		frappe.throw(_('Healthcare Practitioner not available on {0}').format(weekday), title=_('Not Available'))

	return {
		'slot_details': slot_details,
		'present_events': present_events
	}



def check_employee_wise_availability(date, practitioner_doc):
	employee = None
	if practitioner_doc.employee:
		employee = practitioner_doc.employee
	elif practitioner_doc.user_id:
		employee = frappe.db.get_value('Employee', {'user_id': practitioner_doc.user_id}, 'name')

	if employee:
		# check holiday
		if is_holiday(employee, date):
			frappe.throw(_('{0} is a holiday'.format(date)), title=_('Not Available'))

		# check leave status
		leave_record = frappe.db.sql("""select half_day from `tabLeave Application`
			where employee = %s and %s between from_date and to_date
			and docstatus = 1""", (employee, date), as_dict=True)
		if leave_record:
			if leave_record[0].half_day:
				frappe.throw(_('{0} is on a Half day Leave on {1}').format(practitioner_doc.name, date), title=_('Not Available'))
			else:
				frappe.throw(_('{0} is on Leave on {1}').format(practitioner_doc.name, date), title=_('Not Available'))

def get_present_event(practitioner, date):
	present_events = frappe.db.sql("""
		select
			name, availability, from_time, to_time, from_date, to_date, duration, service_unit, repeat_this_event, repeat_on, repeat_till,
			monday, tuesday, wednesday, thursday, friday, saturday, sunday
		from
			`tabPractitioner Availability`
		where
			practitioner = %(practitioner)s and present = 1 and
			(
				(repeat_this_event = 1 and (from_date<=%(date)s and ifnull(repeat_till, "3000-01-01")>=%(date)s))
				or
				(repeat_this_event != 1 and (from_date<=%(date)s and to_date>=%(date)s))
			)
		order by
			from_date, from_time
	""".format(),{"practitioner":practitioner, "date":getdate(date)}, as_dict=True)
	return present_events if present_events else ''

def get_absent_event(practitioner,date):
	# Absent events
	absent_events = frappe.db.sql("""
		select
			name, availability, from_time, to_time, from_date, to_date, duration, service_unit, service_unit, repeat_this_event, repeat_on, repeat_till,
			monday, tuesday, wednesday, thursday, friday, saturday, sunday
		from
			`tabPractitioner Availability`
		where
			practitioner = %(practitioner)s and present != 1 and
			(
				(repeat_this_event = 1 and (from_date<=%(date)s and ifnull(repeat_till, "3000-01-01")>=%(date)s))
				or
				(repeat_this_event != 1 and (from_date<=%(date)s and to_date>=%(date)s))
			)
	""".format(),{"practitioner": practitioner, "date": getdate(date)}, as_dict=True)

	if absent_events:
		remove_events, add_events = remove_events_by_repeat_on(absent_events,date)
		for e in remove_events:
			absent_events.remove(e)
		absent_events = absent_events + add_events
	return absent_events if absent_events else []

def get_available_slots(practitioner_doc, date):
	available_slots = []
	slot_details = []
	weekday = date.strftime('%A')
	practitioner = practitioner_doc.name

	for schedule_entry in practitioner_doc.practitioner_schedules:
		if schedule_entry.schedule:
			practitioner_schedule = frappe.get_doc('Practitioner Schedule', schedule_entry.schedule)
		else:
			frappe.throw(_('{0} does not have a Healthcare Practitioner Schedule. Add it in Healthcare Practitioner').format(
				frappe.bold(practitioner)), title=_('Practitioner Schedule Not Found'))

		if practitioner_schedule:
			available_slots = []
			for time_slot in practitioner_schedule.time_slots:
				if weekday == time_slot.day:
					available_slots.append(time_slot)

			if available_slots:
				appointments = []
				allow_overlap = 0
				service_unit_capacity = 0
				# fetch all appointments to practitioner by service unit
				filters = {
					'practitioner': practitioner,
					'service_unit': schedule_entry.service_unit,
					'appointment_date': date,
					'status': ['not in',['Cancelled']]
				}

				if schedule_entry.service_unit:
					slot_name  = schedule_entry.schedule + ' - ' + schedule_entry.service_unit
					allow_overlap, service_unit_capacity = frappe.get_value('Healthcare Service Unit', schedule_entry.service_unit, ['overlap_appointments', 'total_service_unit_capacity'])
					if not allow_overlap:
						# fetch all appointments to service unit
						filters.pop('practitioner')
				else:
					slot_name = schedule_entry.schedule
					# fetch all appointments to practitioner without service unit
					filters['practitioner'] = practitioner
					filters.pop('service_unit')

				appointments = frappe.get_all(
					'Patient Appointment',
					filters=filters,
					fields=['name', 'appointment_time', 'duration', 'status'])

				absent_events = get_absent_event(practitioner, date)

				slot_details.append({'slot_name':slot_name, 'service_unit':schedule_entry.service_unit, 'absent_events': absent_events,
					'avail_slot':available_slots, 'appointments': appointments,  'allow_overlap': allow_overlap, 'service_unit_capacity':service_unit_capacity})

	return slot_details
def get_present_event_slots(present_events, date, practitioner):
	present_events_details = []
	if present_events:
		remove_events, add_events = remove_events_by_repeat_on(present_events, date)
		for e in remove_events:
			present_events.remove(e)
		present_events = present_events + add_events

		for present_event in present_events:
			event_available_slots = []
			total_time_diff = time_diff_in_seconds(present_event.to_time, present_event.from_time)/60
			from_time = present_event.from_time
			slot_name = present_event.availability
			for x in range(0, int(total_time_diff), present_event.duration):
				to_time = from_time + datetime.timedelta(seconds=present_event.duration*60)
				event_available_slots.append({'from_time': from_time, 'to_time': to_time})
				from_time = to_time
			appointments = []
			if event_available_slots:
				appointments = []
				allow_overlap = 0
				service_unit_capacity = 0
				# fetch all appointments to practitioner by service unit
				filters = {
					'practitioner': practitioner,
					'service_unit': present_event.service_unit,
					'appointment_date': date,
					'status': ['not in',['Cancelled']]
				}

				if present_event.service_unit:
					slot_name  = slot_name+" - "+present_event.service_unit
					allow_overlap, service_unit_capacity = frappe.get_value('Healthcare Service Unit', present_event.service_unit, ['overlap_appointments', 'total_service_unit_capacity'])
					if not allow_overlap:
						# fetch all appointments to service unit
						filters.pop('practitioner')
				else:
					# fetch all appointments to practitioner without service unit
					filters['practitioner'] = practitioner
					filters.pop('service_unit')

				appointments = frappe.get_all(
					'Patient Appointment',
					filters=filters,
					fields=['name', 'appointment_time', 'duration', 'status'],
					order_by= "appointment_date, appointment_time")

				absent_events = get_absent_event(practitioner, date)

				present_events_details.append({'slot_name': slot_name, "service_unit":present_event.service_unit, 'availability': present_event.name,
				'avail_slot': event_available_slots, 'appointments': appointments, 'absent_events': absent_events, 'allow_overlap': allow_overlap, 'service_unit_capacity':service_unit_capacity})
	return present_events_details

def remove_events_by_repeat_on(events_list, date):
	remove_events = []
	add_events = []

	weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
	if events_list:
		i = 0
		for event in events_list:
			if event.repeat_this_event:
				if event.repeat_on == 'Every Day':
					if event[weekdays[getdate(date).weekday()]]:
						add_events.append(event.copy())
					remove_events.append(event.copy())

				if event.repeat_on=='Every Week':
					if getdate(event.from_date).weekday() == getdate(date).weekday():
						add_events.append(event.copy())
					remove_events.append(event.copy())

				if event.repeat_on=='Every Month':
					if getdate(event.from_date).day == getdate(date).day:
						add_events.append(event.copy())
					remove_events.append(event.copy())

				if event.repeat_on=='Every Year':
					if getdate(event.from_date).strftime('%j') == getdate(date).strftime('%j'):
						add_events.append(event.copy())
					remove_events.append(event.copy())
	return remove_events, add_events

@frappe.whitelist()
def update_status(appointment_id, status):
	frappe.db.set_value('Patient Appointment', appointment_id, 'status', status)
	appointment_booked = True
	if status == 'Cancelled':
		appointment_booked = False
		cancel_appointment(appointment_id)

	procedure_prescription = frappe.db.get_value('Patient Appointment', appointment_id, 'procedure_prescription')
	if procedure_prescription:
		frappe.db.set_value('Procedure Prescription', procedure_prescription, 'appointment_booked', appointment_booked)


def send_confirmation_msg(doc):
	if frappe.db.get_single_value('Healthcare Settings', 'send_appointment_confirmation'):
		message = frappe.db.get_single_value('Healthcare Settings', 'appointment_confirmation_msg')
		try:
			send_message(doc, message)
		except Exception:
			frappe.log_error(frappe.get_traceback(), _('Appointment Confirmation Message Not Sent'))
			frappe.msgprint(_('Appointment Confirmation Message Not Sent'), indicator='orange')


@frappe.whitelist()
def make_encounter(source_name, target_doc=None):
	doc = get_mapped_doc('Patient Appointment', source_name, {
		'Patient Appointment': {
			'doctype': 'Patient Encounter',
			'field_map': [
				['appointment', 'name'],
				['patient', 'patient'],
				['practitioner', 'practitioner'],
				['medical_department', 'department'],
				['patient_sex', 'patient_sex'],
				['invoiced', 'invoiced'],
				['company', 'company']
			]
		}
	}, target_doc)
	return doc


def send_appointment_reminder():
	if frappe.db.get_single_value('Healthcare Settings', 'send_appointment_reminder'):
		remind_before = datetime.datetime.strptime(frappe.db.get_single_value('Healthcare Settings', 'remind_before'), '%H:%M:%S')
		reminder_dt = datetime.datetime.now() + datetime.timedelta(
			hours=remind_before.hour, minutes=remind_before.minute, seconds=remind_before.second)

		appointment_list = frappe.db.get_all('Patient Appointment', {
			'appointment_datetime': ['between', (datetime.datetime.now(), reminder_dt)],
			'reminded': 0,
			'status': ['!=', 'Cancelled']
		})

		for appointment in appointment_list:
			doc = frappe.get_doc('Patient Appointment', appointment.name)
			message = frappe.db.get_single_value('Healthcare Settings', 'appointment_reminder_msg')
			send_message(doc, message)
			frappe.db.set_value('Patient Appointment', doc.name, 'reminded', 1)

def send_message(doc, message):
	patient_mobile = frappe.db.get_value('Patient', doc.patient, 'mobile')
	if patient_mobile:
		context = {'doc': doc, 'alert': doc, 'comments': None}
		if doc.get('_comments'):
			context['comments'] = json.loads(doc.get('_comments'))

		# jinja to string convertion happens here
		message = frappe.render_template(message, context)
		number = [patient_mobile]
		try:
			send_sms(number, message)
		except Exception as e:
			frappe.msgprint(_('SMS not sent, please check SMS Settings'), alert=True)

@frappe.whitelist()
def get_events(start, end, filters=None):
	"""Returns events for Gantt / Calendar view rendering.

	:param start: Start date-time.
	:param end: End date-time.
	:param filters: Filters (JSON).
	"""
	from frappe.desk.calendar import get_event_conditions
	conditions = get_event_conditions('Patient Appointment', filters)

	data = frappe.db.sql("""
		select
		`tabPatient Appointment`.name, `tabPatient Appointment`.patient, `tabPatient Appointment`.title,
		`tabPatient Appointment`.practitioner, `tabPatient Appointment`.status,
		`tabPatient Appointment`.duration,
		timestamp(`tabPatient Appointment`.appointment_date, `tabPatient Appointment`.appointment_time) as 'start',
		`tabAppointment Type`.color
		from
		`tabPatient Appointment`
		left join `tabAppointment Type` on `tabPatient Appointment`.appointment_type=`tabAppointment Type`.name
		where
		(`tabPatient Appointment`.appointment_date between %(start)s and %(end)s)
		and `tabPatient Appointment`.status != 'Cancelled' and `tabPatient Appointment`.docstatus < 2 {conditions}""".format(conditions=conditions),
		{"start": start, "end": end}, as_dict=True, update={"allDay": 0})

	for item in data:
		item.end = item.start + datetime.timedelta(minutes = item.duration)

	return data


@frappe.whitelist()
def get_procedure_prescribed(patient):
	return frappe.db.sql(
		"""
			SELECT
				pp.name, pp.procedure, pp.parent, ct.practitioner,
				ct.encounter_date, pp.practitioner, pp.date, pp.department, ct.source, ct.referring_practitioner
			FROM
				`tabPatient Encounter` ct, `tabProcedure Prescription` pp
			WHERE
				ct.patient=%(patient)s and pp.parent=ct.name and pp.appointment_booked=0
			ORDER BY
				ct.creation desc
		""", {'patient': patient}
	)


@frappe.whitelist()
def get_prescribed_therapies(patient):
	return frappe.db.sql(
		"""
			SELECT
				t.therapy_type, t.name, t.parent, e.practitioner,
				e.encounter_date, e.therapy_plan, e.medical_department, e.source, e.referring_practitioner
			FROM
				`tabPatient Encounter` e, `tabTherapy Plan Detail` t
			WHERE
				e.patient=%(patient)s and t.parent=e.name
			ORDER BY
				e.creation desc
		""", {'patient': patient}
	)


def update_appointment_status():
	# update the status of appointments daily
	appointments = frappe.get_all('Patient Appointment', {
		'status': ('not in', ['Closed', 'Cancelled'])
	}, as_dict=1)

	for appointment in appointments:
		frappe.get_doc('Patient Appointment', appointment.name).set_status()
