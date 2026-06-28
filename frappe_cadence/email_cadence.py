import frappe
from frappe import _
import json
import hmac
import hashlib
from markdownify import markdownify as md

class LazyNotesList:
	def __init__(self, doctype, name):
		self.doctype = doctype
		self.name = name
		self._notes = None

	def _load(self):
		if self._notes is None:
			self._notes = frappe.get_all(
				"FCRM Note",
				filters={"reference_doctype": self.doctype, "reference_docname": self.name},
				fields=["*"]
			)
		return self._notes

	def __iter__(self):
		return iter(self._load() or [])

	def __len__(self):
		return len(self._load() or [])

	def __bool__(self):
		return bool(self._load())


class LazyDocumentLink(str):
	def __new__(cls, name, doctype):
		obj = super().__new__(cls, name or "")
		obj.doctype = doctype
		obj.docname = name
		obj._doc = None
		obj._as_dict = None
		return obj

	def _load(self):
		if self._as_dict is None:
			if not self.docname:
				self._as_dict = {}
				return self._as_dict
			try:
				self._doc = frappe.get_doc(self.doctype, self.docname)
				self._as_dict = self._doc.as_dict()
			except Exception:
				self._as_dict = {}
		return self._as_dict

	def __getattr__(self, key):
		if key in ("doctype", "docname", "_doc", "_as_dict", "_load"):
			return super().__getattribute__(key)

		data = self._load()
		if key in data:
			val = data[key]

			if val and isinstance(val, str):
				meta = frappe.get_meta(self.doctype)
				df = meta.get_field(key)
				if df:
					if df.fieldtype == "Link":
						lazy_val = LazyDocumentLink(val, df.options)
						data[key] = lazy_val
						return lazy_val
					elif df.fieldtype == "Dynamic Link":
						target_doctype = data.get(df.options)
						if target_doctype:
							lazy_val = LazyDocumentLink(val, target_doctype)
							data[key] = lazy_val
							return lazy_val

			return val

		if key == "fcrm_notes":
			if "fcrm_notes" not in data:
				data["fcrm_notes"] = LazyNotesList(self.doctype, self.docname)
			return data["fcrm_notes"]

		return None


class LazyProp:
	def __init__(self, doc_link, key):
		self.doc_link = doc_link
		self.key = key

	def _val(self):
		return getattr(self.doc_link, self.key, None)

	def __str__(self):
		val = self._val()
		return str(val) if val is not None else ""

	def __bool__(self):
		return bool(self._val())

	def __iter__(self):
		v = self._val()
		if not v:
			return iter([])
		return iter(v)

	def __getattr__(self, key):
		val = self._val()
		if val is None:
			return None
		return getattr(val, key)


def build_field_tree(fields):
	tree = {}
	for f in fields:
		parts = f.split(".")
		current = tree
		for part in parts:
			if part not in current:
				current[part] = {}
			current = current[part]
	return tree

def enrich_doc(doc_dict, doctype, field_tree):
	if not field_tree:
		return
		
	meta = frappe.get_meta(doctype)
	
	for fieldname, sub_tree in field_tree.items():
		if fieldname == "*":
			continue
			
		if fieldname == "fcrm_notes":
			docname = doc_dict.get("name")
			if docname:
				doc_dict["fcrm_notes"] = frappe.get_all(
					"FCRM Note", 
					filters={"reference_doctype": doctype, "reference_docname": docname}, 
					fields=["*"]
				)
			continue
			
		df = meta.get_field(fieldname)
		if not df:
			continue
			
		value = doc_dict.get(fieldname)
		if not value:
			continue
			
		if df.fieldtype == "Link":
			target_doctype = df.options
			try:
				linked_doc = frappe.get_cached_doc(target_doctype, value)
				if not isinstance(doc_dict[fieldname], dict):
					doc_dict[fieldname] = {"name": value}
				linked_dict = linked_doc.as_dict()
				if "*" in sub_tree:
					doc_dict[fieldname].update(linked_dict)
				else:
					for k in sub_tree:
						if k in linked_dict and k != "*":
							doc_dict[fieldname][k] = linked_dict[k]
				enrich_doc(doc_dict[fieldname], target_doctype, sub_tree)
			except frappe.DoesNotExistError:
				pass
				
		elif df.fieldtype == "Dynamic Link":
			target_doctype = doc_dict.get(df.options)
			if target_doctype:
				try:
					linked_doc = frappe.get_cached_doc(target_doctype, value)
					if not isinstance(doc_dict[fieldname], dict):
						doc_dict[fieldname] = {"name": value}
					linked_dict = linked_doc.as_dict()
					if "*" in sub_tree:
						doc_dict[fieldname].update(linked_dict)
					else:
						for k in sub_tree:
							if k in linked_dict and k != "*":
								doc_dict[fieldname][k] = linked_dict[k]
					enrich_doc(doc_dict[fieldname], target_doctype, sub_tree)
				except frappe.DoesNotExistError:
					pass
					
		elif df.fieldtype == "Table":
			target_doctype = df.options
			for child_dict in value:
				if isinstance(child_dict, dict):
					enrich_doc(child_dict, target_doctype, sub_tree)


@frappe.whitelist()
def get(name=None, filters=None, fields=None):
	"""
	Highly efficient endpoint for n8n to fetch all context in a single network request.
	Returns the exact Email Cadence document structure, dynamically enriching fields based
	on dot-notation parameters (e.g. recipient.*, recipient.organization.*, etc.).
	Accepts either 'name' directly, or standard Frappe 'filters'.
	"""
	child_filters = []
	
	if fields:
		if isinstance(fields, str):
			fields = json.loads(fields)
	else:
		fields = ["*"]

	if filters:
		if isinstance(filters, str):
			filters = json.loads(filters)
			
		parent_filters = []
		for f in filters:
			if len(f) >= 4 and f[0] == "Cadence Email Schedule":
				child_filters.append(f)
			else:
				parent_filters.append(f)

		if parent_filters and not name:
			matched_cadences = frappe.get_all("Email Cadence", filters=parent_filters, pluck="name", limit=1)
			if not matched_cadences:
				frappe.throw(_("Email Cadence not found matching filters"), frappe.DoesNotExistError)
			name = matched_cadences[0]
			
	if not name:
		frappe.throw(_("Please provide name or filters"), frappe.ValidationError)
		
	cadence = frappe.get_doc("Email Cadence", name)
	payload = cadence.as_dict()
	
	field_tree = build_field_tree(fields)
	enrich_doc(payload, "Email Cadence", field_tree)
	
	# Dynamically weave Apollo Sequence Config if cadence_name exists
	step_map = {}
	if cadence.cadence_name and cadence.sender:
		sequence = frappe.get_all(
			"Sequence",
			filters={"cadence": cadence.cadence_name, "sender": cadence.sender},
			fields=["name", "emailer_cadence_id", "email_account_id"],
			limit=1
		)
		if sequence:
			payload["emailer_cadence_id"] = sequence[0].emailer_cadence_id
			payload["email_account_id"] = sequence[0].email_account_id
			
			seq_steps = frappe.get_all(
				"Sequence Step",
				filters={"parent": sequence[0].name},
				fields=["idx", "subject_custom_field_id", "response_custom_field_id"]
			)
			step_map = {str(step.idx): step for step in seq_steps}

	# Prepare Jinja Context (kept separate from payload so n8n only gets rendered prompts)
	context = payload.copy()
	
	if cadence.email_cadence_for and cadence.recipient:
		lead_link = LazyDocumentLink(cadence.recipient, cadence.email_cadence_for)
		
		# Lazily populate the context with Recipient fields
		meta = frappe.get_meta(cadence.email_cadence_for)
		for f in meta.fields:
			context[f.fieldname] = LazyProp(lead_link, f.fieldname)
			
		standard_fields = ["name", "owner", "creation", "modified", "modified_by"]
		for f in standard_fields:
			context[f] = LazyProp(lead_link, f)
			
		context["fcrm_notes"] = LazyProp(lead_link, "fcrm_notes")
		context["recipient"] = lead_link # Keep it available via {{ recipient.first_name }} too

	# Filter and Enrich Cadence Email Schedules
	filtered_schedules = []
	for schedule in payload.get("cadence_email_schedules", []):
		if child_filters:
			match = True
			for cf in child_filters:
				fieldname, operator, value = cf[1], cf[2], cf[3]
				if operator == "=" and str(schedule.get(fieldname)) != str(value):
					match = False
					break
			if not match:
				continue

		template_dict = schedule.get("email_template")
		if isinstance(template_dict, dict):
			# Render prompts if they exist
			if template_dict.get("user_prompt"):
				rendered_html = frappe.render_template(template_dict["user_prompt"], context)
				template_dict["user_prompt"] = md(rendered_html).strip()
			
			if template_dict.get("system_prompt"):
				rendered_html = frappe.render_template(template_dict["system_prompt"], context)
				template_dict["system_prompt"] = md(rendered_html).strip()

		# Dynamically weave Step IDs
		s_idx = str(schedule.get("idx"))
		if s_idx in step_map:
			schedule["subject_apollo_id"] = step_map[s_idx].subject_custom_field_id
			schedule["response_apollo_id"] = step_map[s_idx].response_custom_field_id
			
		filtered_schedules.append(schedule)

	payload["cadence_email_schedules"] = filtered_schedules
	return payload


@frappe.whitelist()
def update(name=None, filters=None, cadence_email_schedules=None, integration_request_id=None):
	"""
	API for n8n to update email schedules.
	Accepts filters as query parameters to locate the Cadence, updates the schedule, and resolves the Integration Request.
	"""
	if frappe.session.user == "Guest":
		cadence_agent_webhook_secret = frappe.conf.get("cadence_agent_webhook_secret")
		if cadence_agent_webhook_secret:
			if not hasattr(frappe, "request") or not frappe.request:
				frappe.throw(_("Invalid request context for webhook verification"), frappe.PermissionError)
				
			signature = frappe.request.headers.get("X-Frappe-Webhook-Signature")
			if not signature:
				frappe.throw(_("Missing X-Frappe-Webhook-Signature header"), frappe.PermissionError)
				
			payload = frappe.request.get_data()
			
			expected_signature = hmac.new(
				cadence_agent_webhook_secret.encode("utf-8"),
				payload,
				hashlib.sha256
			).hexdigest()
			
			if not hmac.compare_digest(signature, expected_signature):
				frappe.throw(_("Invalid Webhook Signature"), frappe.PermissionError)
		else:
			frappe.throw(_("Webhook secret not configured. Agent integration requires cadence_agent_webhook_secret in site config."), frappe.PermissionError)

	if filters:
		if isinstance(filters, str):
			filters = json.loads(filters)
		matched_cadences = frappe.get_all("Email Cadence", filters=filters, pluck="name", limit=1)
		if matched_cadences:
			name = matched_cadences[0]

	if not name:
		frappe.throw(_("Could not locate Email Cadence via name or filters."))
		
	cadence = frappe.get_doc("Email Cadence", name)
	
	if cadence.status not in ["", None, "Draft"]:
		# Ignore retry requests if already generated or failed to prevent Convoy from getting stuck in a retry loop
		return {"status": "ignored", "reason": "Cadence status is already {0}".format(cadence.status)}
	
	if isinstance(cadence_email_schedules, str):
		cadence_email_schedules = json.loads(cadence_email_schedules)
		
	# if a single dictionary is passed instead of a list, wrap it in a list
	if isinstance(cadence_email_schedules, dict):
		cadence_email_schedules = [cadence_email_schedules]
		
	for s_data in cadence_email_schedules:
		for s in cadence.cadence_email_schedules:
			# match by name or by idx
			if s.name == s_data.get("name") or (s_data.get("idx") and s.idx == int(s_data.get("idx"))):
				# Dynamically update any field provided in the payload
				for field_name, value in s_data.items():
					if field_name not in ["name", "idx"]:
						s.set(field_name, value)
				break
	
	cadence.flags.ignore_validate = True
	cadence.save(ignore_permissions=True)

	# Complete the Integration Request audit log
	if integration_request_id:
		doc = frappe.get_doc("Integration Request", integration_request_id)
		if doc.status != "Completed":
			doc.handle_success({"cadence_email_schedules": cadence_email_schedules})

	return {"status": "success"}
