__author__ = 'Koji'

from validator import Validator

from api.error.application_error import ApplicationError
from api.error.invalid_parameter_error import InvalidParameterError 


class PlatformValidator(Validator):
	@classmethod
	def valid_platforms_params(self, request, args, kw):
		try:
			if not self.valid_unit_id(kw['unit_id']):
				raise InvalidParameterError(exp, 'Unit ID')

			return True

		except InvalidParameterError as ipexp:
			raise ipexp

		except Exception as exp:
			raise ApplicationError(exp, 'An unexpected error has occurred.')
