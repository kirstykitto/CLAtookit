__author__ = 'Koji'

from ..endpoint.timeseries import Timeseries
from xapi.statement.xapi_settings import xapi_settings
from common.util import Utility
from validator import Validator

from api.error.application_error import ApplicationError
from api.error.invalid_parameter_error import InvalidParameterError 


class TimeseriesValidator(Validator):
	# Parameter validation 
	@classmethod
	def valid_timeseries_params(self, request, args, kw):
		try:
			if not self.valid_unit_id(kw['unit_id']):
				raise InvalidParameterError(exp, 'Unit ID')

			# TODO: validate user (implement it later?)
			# Validate a user
			# ts_prop.user = None
			
			if not self.valid_date(request.GET.get('start', None), '%Y-%m-%d'):
				raise InvalidParameterError(None, 'Start date')

			if not self.valid_date(request.GET.get('end', None), '%Y-%m-%d'):
				raise InvalidParameterError(None, 'End date')

			if request.GET.get('order', None) and \
				(request.GET.get('order', None) != Timeseries.STR_ORDER_BY_DATE \
					and request.GET.get('order', None) != '-' + Timeseries.STR_ORDER_BY_DATE):
				raise InvalidParameterError(None, 'Order By')

			if kw['type'] == 'verb':
				if not self.valid_verb_names(request.GET.get('filter', None), kw['unit_id']):
					raise InvalidParameterError(None, 'Filter')
				if not self.valid_platform_names(request.GET.get('platforms', None), kw['unit_id']):
					raise InvalidParameterError(None, 'Platforms')

			elif kw['type'] == 'platform':
				if not self.valid_platform_names(request.GET.get('filter', None), kw['unit_id']):
					raise InvalidParameterError(None, 'Filter')

			return True

		except InvalidParameterError as ipexp:
			raise ipexp

		except Exception as exp:
			raise ApplicationError(exp, 'An unexpected error has occurred.')
