# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Cadence(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from frappe_cadence.cadence.doctype.cadence_multi_channel_schedule.cadence_multi_channel_schedule import (
			CadenceMultiChannelSchedule,
		)

		cadence_name: DF.Data
		cadence_schedules: DF.Table[CadenceMultiChannelSchedule]
		description: DF.Text | None
		cadence_code: DF.Data
		naming_series: DF.Literal["CAD-.YYYY.-"]
	# end: auto-generated types

	def autoname(self):
		if not self.cadence_code:
			from frappe.model.naming import set_name_by_naming_series
			set_name_by_naming_series(self)
			self.cadence_code = self.name
		self.name = self.cadence_code

	def after_insert(self):
		if frappe.db.exists("UTM Campaign", self.name):
			mc = frappe.get_doc("UTM Campaign", self.name)
		else:
			mc = frappe.new_doc("UTM Campaign")
			mc.name = self.name
		mc.cadence_description = self.description
		mc.crm_cadence = self.name
		mc.save(ignore_permissions=True)

	def on_change(self):
		if frappe.db.exists("UTM Campaign", self.name):
			mc = frappe.get_doc("UTM Campaign", self.name)
		else:
			mc = frappe.new_doc("UTM Campaign")
			mc.name = self.name
		mc.cadence_description = self.description
		mc.crm_cadence = self.name
		mc.save(ignore_permissions=True)

	def on_update(self):
		frappe.enqueue(
			"frappe_cadence.cadence.doctype.cadence.cadence.update_sequences",
			queue="long",
			cadence_name=self.name,
		)

def update_sequences(cadence_name):
	sequences = frappe.get_all("Sequence", filters={"cadence": cadence_name}, pluck="name")
	for seq_name in sequences:
		seq = frappe.get_doc("Sequence", seq_name)
		seq.populate_sequence_steps()
		seq.save(ignore_permissions=True)
