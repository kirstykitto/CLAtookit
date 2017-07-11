from django.http import HttpResponse

from datetime import datetime
from isodate.isodatetime import parse_datetime, parse_date


class Utility(object):
	@classmethod
	def get_site_url(self, request):
		protocol = 'https' if request.is_secure() else 'http'
		url = '%s://%s' % (protocol, request.get_host())
		return url


	@classmethod
	def convert_to_datetime_object(self, timestr):
		try:
			date_object = parse_datetime(timestr)
		except ValueError as e:
			raise ParamError("An error has occurred. Time format does not match. %s -- Error: %s" % (timestr, e.message))

		return date_object


	@classmethod
	def format_date(self, date_str, splitter, connector, isMonthSubtract):
		ret = ''
		if date_str is None or date_str == '':
			return ret

		# If isMonthSubtract is True, then subtract 1 from month (to avoid calculation in JavaScript)
		# isMonthSubtract = True is recommended
		month_subtract = 1 if isMonthSubtract else 0
		dateAry = date_str.split(splitter)
		return dateAry[0] + connector + str(int(dateAry[1]) - month_subtract).zfill(2) + connector + dateAry[2]


	@classmethod
	def convert_unixtime_to_datetime(self, unix_time):
		unix_time = float(unix_time)
		return datetime.fromtimestamp(unix_time)


	@classmethod
	def validate_date(self, datestr, format_string):
		date_object = None
		try:
			date_object = self.convert_to_date_object(datestr, format_string)
		except ValueError:
			raise ValueError("Incorrect data format. It must be YYYY-MM-DD")

		ret = True if date_object else False
		return ret


	@classmethod
	def convert_to_date_object(self, datestr, format_string):
		date_object = None
		try:
			date_object = datetime.strptime(datestr, format_string)
		except ValueError as ve:
			print type(ve)
			print ve.args
			raise ve

		return date_object


	@classmethod
	def compare_to(self, d1, d2):
		if d1 is None and d2 is None:
			return 0
		elif d1 is None and d2 is not None:
			return -1
		elif d1 is not None and d2 is None:
			return 1

		date1 = d1
		date2 = d2
		if not isinstance(date1, datetime):
			date1 = self.convert_to_date_object(str(d1), '%Y-%m-%d')
		if not isinstance(date2, datetime):
			date2 = self.convert_to_date_object(str(d2), '%Y-%m-%d')

		if date1 == date2:
			return 0
		elif date1 < date2:
			return -1
		elif date1 > date2:
			return 1


	@classmethod
	def max_date(self, d1, d2):
		if d1 is None and d2 is not None:
			return d2
		elif d1 is not None and d2 is None:
			return d1

		if self.compare_to(d1, d2) == 1:
			return d1
		elif self.compare_to(d1, d2) == -1:
			return d2
		else:
			return d1


	@classmethod
	def min_date(self, d1, d2):
		if d1 is None and d2 is not None:
			return d2
		elif d1 is not None and d2 is None:
			return d1

		if self.compare_to(d1, d2) == 1:
			return d2
		elif self.compare_to(d1, d2) == -1:
			return d1
		else:
			return d1

