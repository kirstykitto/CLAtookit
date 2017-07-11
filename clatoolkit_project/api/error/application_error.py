__author__ = 'Koji'

from error import Error

class ApplicationError(Error):

	def __init__(self, expression = None, message = None):
		super(ApplicationError, self).__init__(expression, message)
