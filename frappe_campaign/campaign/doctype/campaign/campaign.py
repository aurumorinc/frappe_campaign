# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import set_name_by_naming_series


class Campaign(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from frappe_campaign.campaign.doctype.campaign_multi_channel_schedule.campaign_multi_channel_schedule import (
			CampaignMultiChannelSchedule,
		)

		campaign_name: DF.Data
		campaign_schedules: DF.Table[CampaignMultiChannelSchedule]
		description: DF.Text | None
		naming_series: DF.Literal["SAL-CAM-.YYYY.-"]
	# end: auto-generated types

	def autoname(self):
		if frappe.defaults.get_global_default("campaign_naming_by") != "Naming Series":
			self.name = self.campaign_name
		else:
			set_name_by_naming_series(self)

	def after_insert(self):
		if frappe.db.exists("UTM Campaign", self.campaign_name):
			mc = frappe.get_doc("UTM Campaign", self.campaign_name)
		else:
			mc = frappe.new_doc("UTM Campaign")
			mc.name = self.campaign_name
		mc.campaign_description = self.description
		mc.crm_campaign = self.campaign_name
		mc.save(ignore_permissions=True)

	def on_change(self):
		if frappe.db.exists("UTM Campaign", self.campaign_name):
			mc = frappe.get_doc("UTM Campaign", self.campaign_name)
		else:
			mc = frappe.new_doc("UTM Campaign")
			mc.name = self.campaign_name
		mc.campaign_description = self.description
		mc.crm_campaign = self.campaign_name
		mc.save(ignore_permissions=True)

	def on_update(self):
		frappe.enqueue(
			"frappe_campaign.campaign.doctype.campaign.campaign.update_sequences",
			queue="long",
			campaign_name=self.name,
		)

def update_sequences(campaign_name):
	sequences = frappe.get_all("Sequence", filters={"campaign": campaign_name}, pluck="name")
	for seq_name in sequences:
		seq = frappe.get_doc("Sequence", seq_name)
		seq.populate_sequence_steps()
		seq.save(ignore_permissions=True)
