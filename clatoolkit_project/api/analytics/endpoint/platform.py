__author__ = 'Koji'

import json


from clatoolkit.models import UnitOffering
from api.error.application_error import ApplicationError


class Platform(object):

	@classmethod
	def get_platforms(self, request, args, kw):
		try:
			unit = UnitOffering.objects.get(id = int(kw['unit_id']))
			platforms = unit.get_required_platforms()
			platforms.sort()
			return {'platforms': platforms}

		except Exception as exp:
			raise ApplicationError(exp, 'An unexpected error has occurred.')

