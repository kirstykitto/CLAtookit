__author__ = 'Koji'

from datetime import datetime


class Error(Exception):
	# Base class for exceptions.

	def __init__(self, expression = None, message = None):
		self.expression = expression
		self.message = message
		self.datetime = datetime.now().strftime("%d/%m/%Y %H:%M:%S.%f")

	def get_errorlog_basic_message(self, error_type = 'error'):
		return '[%s] [%s] ' % (self.datetime, error_type)

	def print_errorlog_message(self):
		message = self.get_errorlog_message()
		if self.expression and self.expression.args:
			message += ' [original error]: %s' % (self.expression.args)

		print message

	def get_errorlog_message(self, additional_msg = ''):
		return '%s%s: %s' % (self.get_errorlog_basic_message('error'), type(self.expression), self.message)

