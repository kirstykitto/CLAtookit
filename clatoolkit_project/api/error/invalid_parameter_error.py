__author__ = 'Koji'

from error import Error

class InvalidParameterError(Error):

	def __init__(self, expression = None, param_name = ''):
		super(InvalidParameterError, self).__init__(expression, 'Invalid parameter: %s' % param_name)
		