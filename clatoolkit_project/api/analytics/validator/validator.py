__author__ = 'Koji'

import re
from ..endpoint.timeseries import Timeseries
from xapi.statement.xapi_settings import xapi_settings
from clatoolkit.models import UnitOffering
from common.util import Utility


class Validator(object):
	@classmethod
	def valid_unit_id(self, unit_id):
		ret = True
		try:
			UnitOffering.objects.get(id = int(unit_id))
		except exp:
			ret = False

		return ret


	@classmethod
	def valid_platform_names(self, platform_filter, unit_id):
		# If the parameter does not match to platform/verb name defined in the toolkit, it is invalid param.
		try:
			unit = UnitOffering.objects.get(id = int(unit_id))
			platform_list = unit.get_required_platforms()
			# Empty string is acceptable
			if platform_filter and platform_filter != '':
				filter_vals = platform_filter.split(',')
				# compare_list = xapi_settings.get_platform_list()
				for val in filter_vals:
					if not val in platform_list and val != 'all':
						return False
		except:
			return False

		return True


	@classmethod
	def valid_verb_names(self, verb_filter, unit_id):
		# If the parameter does not match to platform/verb name defined in the toolkit, it is invalid param.
		try:
			unit = UnitOffering.objects.get(id = int(unit_id))
			verb_list = unit.get_required_verbs()
			# Empty string is acceptable
			if verb_filter and verb_filter != '':
				filter_vals = verb_filter.split(',')
				# compare_list = xapi_settings.get_verb_list()
				for val in filter_vals:
					if not val in verb_list and val != 'all':
						return False
		except:
			return False

		return True


	@classmethod
	def valid_date(self, date_str, format_string):
		try:
			# if date_str and re.match('\d{4}-\d{2}-\d{2}$' , date_str) is None:
			if date_str and Utility.validate_date(date_str, format_string) is None:
				return False
		except:
			return False

		return True

