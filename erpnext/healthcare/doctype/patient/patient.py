# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS LLP and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr, getdate, flt
import dateutil
from frappe.contacts.address_and_contact import load_address_and_contact, delete_contact_and_address
from frappe.model.naming import set_name_by_naming_series
from erpnext.healthcare.doctype.healthcare_settings.healthcare_settings import get_receivable_account,get_income_account,send_registration_sms

class Patient(Document):
	def after_insert(self):
		if(frappe.db.get_value("Healthcare Settings", None, "manage_customer") == '1' and not self.customer):
			create_customer(self)
		if(frappe.db.get_value("Healthcare Settings", None, "collect_registration_fee") == '1'):
			frappe.db.set_value("Patient", self.name, "disabled", 1)
		else:
			send_registration_sms(self)
		self.reload()
	def onload(self):
		load_address_and_contact(self)

	def on_update(self):
		self.add_as_website_user()
		self.update_customer()
		self.add_patient_contact()

	def add_as_website_user(self):
		if(self.email):
			if not frappe.db.exists ("User", self.email):
				user = frappe.get_doc({
					"doctype": "User",
					"first_name": self.patient_name,
					"email": self.email,
					"user_type": "Website User"
				})
				user.flags.ignore_permissions = True
				user.add_roles("Patient")

	def update_customer(self):
		if self.customer:
			customer = frappe.get_doc("Customer", self.customer)
			customer.set("accounts", [])
			for receivable_account in self.receivable_account:
				account_line = customer.append("accounts")
				account_line.company = receivable_account.company
				account_line.account = receivable_account.account
			customer.save(ignore_permissions=True)

	def add_patient_contact(self):
		if(self.email):
			user=frappe.db.exists ("User", self.email)
			if user:
				contact=frappe.get_doc("Contact", {"email_id":self.email})
				if contact:
					contact.is_primary_contact= True
					if self.mobile:
						contact.mobile=self.mobile
					links=[]
					links.append({
						"link_doctype": "Patient",
						"link_name": self.name
					})
					links.append({
						"link_doctype": "Customer",
						"link_name": self.customer
					})
					contact.set("links", links)
					contact.save(ignore_permissions=True)
			else:
				create_new_contact(self)
		else:
			if(self.mobile):
				create_new_contact(self)

	def autoname(self):
		patient_master_name = frappe.defaults.get_global_default('patient_master_name')
		if patient_master_name == 'Patient Name':
			self.name = self.get_patient_name()
		else:
			set_name_by_naming_series(self)

	def get_patient_name(self):
		name = self.patient_name
		if frappe.db.get_value("Patient", name):
			count = frappe.db.sql("""select ifnull(MAX(CAST(SUBSTRING_INDEX(name, ' ', -1) AS UNSIGNED)), 0) from tabPatient
				 where name like %s""", "%{0} - %".format(name), as_list=1)[0][0]
			count = cint(count) + 1
			return "{0} - {1}".format(name, cstr(count))

		return name

	def get_age(self):
		age_str = ""
		if self.dob:
			born = getdate(self.dob)
			age = dateutil.relativedelta.relativedelta(getdate(), born)
			age_str = str(age.years) + " year(s) " + str(age.months) + " month(s) " + str(age.days) + " day(s)"
		return age_str

	def invoice_patient_registration(self):
		frappe.db.set_value("Patient", self.name, "disabled", 0)
		send_registration_sms(self)
		if(flt(frappe.get_value("Healthcare Settings", None, "registration_fee"))>0):
			company = frappe.defaults.get_user_default('company')
			if not company:
				company = frappe.db.get_value("Global Defaults", None, "default_company")
			sales_invoice = make_invoice(self.name, company)
			sales_invoice.save(ignore_permissions=True)
			return {'invoice': sales_invoice.name}
	def get_billing_info(self):
		print("p")
		return get_billing_info(self)

def create_customer(doc):
	customer_group = doc.customer_group
	if not customer_group:
		customer_group = frappe.get_value("Selling Settings", None, "customer_group")
	territory = frappe.get_value("Selling Settings", None, "territory")
	if not (customer_group and territory):
		customer_group = "Commercial"
		territory = "Rest Of The World"
		frappe.msgprint(_("Please set default customer group and territory in Selling Settings"), alert=True)
	customer = frappe.get_doc({"doctype": "Customer",
	"customer_name": doc.patient_name,
	"customer_group": customer_group,
	"territory" : territory,
	"customer_type": "Individual"
	}).insert(ignore_permissions=True)
	frappe.db.set_value("Patient", doc.name, "customer", customer.name)
	frappe.msgprint(_("Customer {0} is created.").format(customer.name), alert=True)

def make_invoice(patient, company):
	sales_invoice = frappe.new_doc("Sales Invoice")
	sales_invoice.customer = frappe.get_value("Patient", patient, "customer")
	sales_invoice.due_date = getdate()
	sales_invoice.company = company
	sales_invoice.is_pos = '0'
	sales_invoice.debit_to = get_receivable_account(company, patient)

	item_line = sales_invoice.append("items")
	item_line.item_name = "Registeration Fee"
	item_line.description = "Registeration Fee"
	item_line.qty = 1
	item_line.uom = "Nos"
	item_line.conversion_factor = 1
	item_line.income_account = get_income_account(None, company)
	item_line.rate = frappe.get_value("Healthcare Settings", None, "registration_fee")
	item_line.amount = item_line.rate
	sales_invoice.set_missing_values()
	return sales_invoice

def create_new_contact(doc):
	contact= frappe.new_doc("Contact")
	contact.first_name=doc.patient_name
	if doc.mobile:
		contact.mobile=doc.mobile
	contact.gender=doc.sex
	contact.status="Passive"
	contact.is_primary_contact= True
	links=[]
	links.append({
		"link_doctype": "Patient",
		"link_name": doc.name
	})
	links.append({
		"link_doctype": "Customer",
		"link_name": doc.customer
	})
	contact.set("links", links)
	contact.insert(ignore_permissions=True)


@frappe.whitelist()
def get_patient_detail(patient):
	patient_dict = frappe.db.sql("""select * from tabPatient where name=%s""", (patient), as_dict=1)
	if not patient_dict:
		frappe.throw(_("Patient not found"))
	vital_sign = frappe.db.sql("""select * from `tabVital Signs` where patient=%s
		order by signs_date desc limit 1""", (patient), as_dict=1)
	details = patient_dict[0]
	if vital_sign:
		details.update(vital_sign[0])
	return details

@frappe.whitelist()
def get_billing_info(doc):
	customer = frappe.db.get_value("Patient", doc.name, 'customer')
	from erpnext.accounts.utils import get_balance_on
	patient_grand_total = frappe.get_all("Sales Invoice",
		filters={
			'docstatus': 1,
			'customer': customer
		},
		fields=["patient", "sum(grand_total) as grand_total", "sum(base_grand_total) as base_grand_total"]
	)
	company = frappe.defaults.get_user_default('company')
	if not company:
		company = frappe.db.get_value("Global Defaults", None, "default_company")
	company_default_currency = frappe.db.get_value("Company", company, 'default_currency')
	from erpnext.accounts.party import get_party_account_currency
	party_account_currency = get_party_account_currency("Customer", customer, company)

	if party_account_currency==company_default_currency:
		billing_this_year = flt(patient_grand_total[0]["base_grand_total"])
	else:
		billing_this_year = flt(patient_grand_total[0]["grand_total"])
	info = {}
	info["total_billing"] = flt(billing_this_year) if billing_this_year else 0
	info["currency"] = party_account_currency
	info["party_balance"] = get_balance_on(party_type="Customer", party=customer)
	return info
