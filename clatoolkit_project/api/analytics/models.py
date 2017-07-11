__author__ = 'Koji'

class AnalysisProperty(object):
	platform = None
	verb = None
	user = None
	unit = None


class TimeseriesProperty(AnalysisProperty):
	start_date = None
	end_date = None
	order_by = None # column name to sort records 
	order = 'asc' 
	month_subtract = True
	filter_string = None
	platform_filter_string = None

