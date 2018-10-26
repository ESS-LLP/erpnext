# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals
import unittest
import frappe
import erpnext
import random
from frappe.utils.make_random import get_random
from frappe.utils import add_months
from erpnext.hr.doctype.employee.test_employee import make_employee
from erpnext.hr.doctype.employee_tax_exemption_declaration.test_employee_tax_exemption_declaration import create_payroll_period
from erpnext.hr.doctype.salary_structure.test_salary_structure import create_salary_structure_assignment

class TestEmployeeBenefitClaim(unittest.TestCase):
	def test_employee_benefit_claim(self):
		employee = make_employee("test_employee@salary.com")

		delete_docs = ["Payroll Period", "Salary Structure", "Salary Component", "Employee Benefit Claim"]
		for doc in delete_docs:
			frappe.db.sql("delete from `tab%s`" % (doc))
		frappe.db.sql("delete from `tabSalary Structure Assignment` where employee='%s'" % (employee))
		make_salary_component(make_earning_salary_component())
		payroll_period = create_payroll_period()
		salary_structure = make_salary_structure("Stucture to test benefit claim", "Monthly", 20000)
		salary_structure_assignment = create_salary_structure_assignment(employee, salary_structure.name, payroll_period.start_date)
		self.test_max_benefit_for_component(employee, payroll_period)
		self.test_max_benefit_for_sal_struct(employee, payroll_period)
		self.test_benefit_claim_amount(employee, payroll_period)
		self.test_non_pro_rata_benefit_claim(employee, payroll_period)

	def test_max_benefit_for_component(self, employee, payroll_period):
		benefit_claim = create_benefit_claim(employee, payroll_period, 5001, 'Tour Allowance')
		self.assertRaises(frappe.ValidationError, benefit_claim.save)
		benefit_claim = create_benefit_claim(employee, payroll_period, 5000, 'Tour Allowance')
		self.assertTrue(benefit_claim.save)

	def test_max_benefit_for_sal_struct(self, employee, payroll_period):
		benefit_claim = create_benefit_claim(employee, payroll_period, 24000, 'Medical Allowance')
		self.assertRaises(frappe.ValidationError, benefit_claim.save)

	def test_benefit_claim_amount(self, employee, payroll_period):
		benefit_claim = create_benefit_claim(employee, payroll_period, 2000, 'Tour Allowance')
		benefit_claim.save()
		benefit_claim.submit()
		benefit_claim = create_benefit_claim(employee, payroll_period, 18001, 'Medical Allowance')
		self.assertRaises(frappe.ValidationError, benefit_claim.save)
		benefit_claim = create_benefit_claim(employee, payroll_period, 18000, 'Medical Allowance')
		self.assertTrue(benefit_claim.save)

	def test_non_pro_rata_benefit_claim(self, employee, payroll_period):
		# Here Leave Travel Allowance is a non pro rata component (ie, pay_against_benefit_claim is 1)
		benefit_claim = create_benefit_claim(employee, payroll_period, 2000, 'Leave Travel Allowance')
		self.assertRaises(frappe.ValidationError, benefit_claim.save)

def make_salary_component(salary_components):
	for salary_component in salary_components:
		if not frappe.db.exists('Salary Component', salary_component["salary_component"]):
			salary_component["doctype"] = "Salary Component"
			component_abc = frappe.get_doc(salary_component).insert()

def make_earning_salary_component():
	data = [
			{
				"salary_component": 'Basic Salary',
				"salary_component_abbr":'BS',
				"condition": 'base > 10000',
				"formula": 'base*.5',
				"type": "Earning",
				"amount_based_on_formula": 1
			},
			{
				"salary_component": 'HRA',
				"salary_component_abbr":'H',
				"amount": 3000,
				"type": "Earning"
			},
			{
				"salary_component": 'Special Allowance',
				"salary_component_abbr":'SA',
				"condition": 'H < 10000',
				"formula": 'BS*.5',
				"type": "Earning",
				"amount_based_on_formula": 1
			},
			{
				"salary_component": "Leave Encashment",
				"salary_component_abbr": 'LE',
				"is_additional_component": 1,
				"type": "Earning"
			},
			{
				"salary_component": "Leave Travel Allowance",
				"salary_component_abbr": 'LTA',
				"is_flexible_benefit": 1,
				"type": "Earning",
				"pay_against_benefit_claim": 1,
				"max_benefit_amount": 5000
			},
			{
				"salary_component": "Tour Allowance",
				"salary_component_abbr": 'TRA',
				"is_flexible_benefit": 1,
				"pay_against_benefit_claim": 0,
				"type": "Earning",
				"max_benefit_amount": 5000
			},
			{
				"salary_component": "Medical Allowance",
				"salary_component_abbr": 'MA',
				"is_flexible_benefit": 1,
				"pay_against_benefit_claim": 0,
				"type": "Earning",
				"max_benefit_amount": 25000
			},
			{
				"salary_component": "Perfomance Bonus",
				"salary_component_abbr": 'PB',
				"is_additional_component": 1,
				"type": "Earning"
			}
		]
	return data

def create_benefit_claim(employee, payroll_period, amount, component):
	claim_date = add_months(payroll_period.start_date, random.randint(0, 11))
	return frappe.get_doc({"doctype": "Employee Benefit Claim", "employee": employee,
		"claimed_amount": amount, "claim_date": claim_date, "earning_component":
		component})

def make_salary_structure(salary_structure, payroll_frequency, max_benefits):
	if not frappe.db.exists('Salary Structure', salary_structure):
		details = {
			"doctype": "Salary Structure",
			"name": salary_structure,
			"company": erpnext.get_default_company(),
			"earnings": make_earning_salary_component(),
			"payroll_frequency": payroll_frequency,
			"max_benefits": max_benefits,
			"payment_account": get_random("Account")
		}
		salary_structure_doc = frappe.get_doc(details).insert()
		salary_structure_doc.submit()
	else:
		salary_structure_doc = frappe.get_doc("Salary Structure", salary_structure)

	return salary_structure_doc
