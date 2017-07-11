__author__ = 'Koji'

import copy
from collections import OrderedDict
from django.db import connection
from ..models import TimeseriesProperty
from common.util import Utility

from clatoolkit.models import UnitOffering
from xapi.statement.xapi_settings import xapi_settings
from api.error.application_error import ApplicationError



class Timeseries(object):
    STR_ORDER_BY_DATE = 'date'


    @classmethod
    def get_platform_timeseries(self, request, args, kw):
        try:
            ts_prop = self.get_timeseries_property(request, args, kw)
            platform_list = self.get_platform_list(ts_prop.filter_string, ts_prop.unit)
            platform_list.sort()

            # Subtract the month because month starts from 0 in JavaScript 
            start = Utility.format_date(
                            str(Utility.max_date(ts_prop.start_date, ts_prop.unit.start_date)),
                            '-', '-', True)
            end = Utility.format_date(
                            str(Utility.min_date(ts_prop.end_date, ts_prop.unit.end_date)),
                            '-', '-', True)
            values = OrderedDict ([
                ('platforms', ','.join(platform_list)),
                ('start', start),
                ('end', end),
                ('activities', self.get_timeseries(ts_prop, platform_list))
            ])

            return values

        except Exception as exp:
            raise ApplicationError(exp, 'An unexpected error has occurred.')
        

    @classmethod
    def get_verb_timeseries(self, request, args, kw):
        try:
            ts_prop = self.get_timeseries_property(request, args, kw)
            verb_list = self.get_verb_list(ts_prop.filter_string, ts_prop.unit, ts_prop.platform_filter_string)
            platform_list = self.get_platform_list(ts_prop.platform_filter_string, ts_prop.unit)
            verb_list.sort()
            platform_list.sort()

            activity_list = []
            for verb in verb_list:
                obj = OrderedDict([
                    ('verb', verb),
                    ('activities', self.get_timeseries(ts_prop, platform_list, verb))
                ])
                activity_list.append(obj)
                
            # Modify the data structure to reduce redundant data (date element)
            # 
            # activity_list has something like this.
            # {
            # "verb": "created",
            # "activities": [{
            #   "date": "2016-08-01",
            #   "Slack": 1,
            #   },{
            # ... 
            # ]},{
            # "verb": "shared",
            # "activities": [{
            #   "date": "2016-08-01",
            #   "Slack": 0,
            # },{
            # ...
            # 
            # date element exist in every activities, which is redundant.
            # The following code eliminate it and changes the structure above to:
            # {
            # "date": "2017-00-01",
            # "commented": {
            #     "Slack": 0,
            #     "Trello": 0
            # },
            # "created": {
            #     "Slack": 0,
            #     "Trello": 0
            # }, 
            # ...
            # 
            new_activity_list = []
            activity = activity_list[0]
            index = 0
            for i in xrange(len(activity['activities'])):
                # Add date in activity_list to a variable
                new_activity = OrderedDict([('date', activity['activities'][i]['date'])])

                for j in xrange(len(activity_list)):
                    inner_activities = activity_list[j]['activities']
                    single_activity = inner_activities[i]
                    # Remove date element so the other elements can be retrieve easily
                    single_activity.pop('date', None)

                    obj = OrderedDict([])
                    for key in single_activity.keys():
                        obj[key] = single_activity[key]

                    new_activity[activity_list[j]['verb']] = obj

                new_activity_list.append(new_activity)

            # Replace the old list with the new one
            activity_list = new_activity_list

            # Subtract the month because month starts from 0 in JavaScript 
            start = Utility.format_date(
                            str(Utility.max_date(ts_prop.start_date, ts_prop.unit.start_date)),
                            '-', '-', True)
            end = Utility.format_date(
                            str(Utility.min_date(ts_prop.end_date, ts_prop.unit.end_date)),
                            '-', '-', True)

            values = OrderedDict ([
                ('verbs', ','.join(verb_list)),
                ('platforms', ','.join(platform_list)),
                ('start', start),
                ('end', end),
                ('activities', activity_list)
            ])

            return values

        except Exception as exp:
            raise ApplicationError(exp, 'An unexpected error has occurred.')


    @classmethod
    def get_platform_list(self, platform_filter_string, unit):
        platform_list = []
        # When "all" is specified
        if platform_filter_string:
            if platform_filter_string.find('all') != -1:
                platform_list = unit.get_required_platforms()
            else:
                platform_list = platform_filter_string.split(',')
        else:
            platform_list = unit.get_required_platforms()

        return platform_list


    @classmethod
    def get_verb_list(self, verb_filter_string, unit, platform_filter_string = None):
        verb_list = []
        platform_list = []
        if platform_filter_string:
            platform_list = platform_filter_string.split(',')

        if verb_filter_string:
            if verb_filter_string.find('all') != -1:
                verb_list = unit.get_required_verbs()
            else:
                verb_list = verb_filter_string.split(',')
        else:
            verb_list = unit.get_required_verbs(platform_list = platform_list)

        return verb_list


    @classmethod
    def get_timeseries_property(self, request, args, kw, month_subtract = True):
        ts_prop = TimeseriesProperty()
        ts_prop.unit = UnitOffering.objects.get(id = int(kw['unit_id']))
        ts_prop.user = None
        ts_prop.start_date = request.GET.get('start', None)
        ts_prop.end_date = request.GET.get('end', None)
        ts_prop.month_subtract = month_subtract
        ts_prop.order_by, ts_prop.order = self.get_orderby(request.GET.get('order', None))
        ts_prop.filter_string = request.GET.get('filter', None)
        platforms = request.GET.get('platforms', None)
        ts_prop.platform_filter_string = platforms if platforms is not None and platforms != 'all' else 'all'
        return ts_prop


    @classmethod
    def get_timeseries(self, ts_prop, platform_list, verb = None):
        sql = self.get_timeseries_sql(ts_prop, platform_list, verb)
        # print sql

        cursor = connection.cursor()
        cursor.execute(sql)
        result = cursor.fetchall()
        activities = []

        record_count = self.get_series_record_count(ts_prop.unit, ts_prop.start_date, ts_prop.end_date)
        # for row in result:
        for i in xrange(record_count):
            index = 0
            activity = OrderedDict([('date', '')]) # Add date element
            for platform in platform_list:
                row = result[i + (index * record_count) ]
                curdate = row[1]
                activity[platform] = int(row[2])
                index += 1

            # In JavaScript, month starts at 0, thus subtract 1 from the month if month_subtract is True
            month = curdate.month -1 if ts_prop.month_subtract else curdate.month
            activity['date'] = "%s-%s-%s" % (curdate.year, '%02d' % month, '%02d' % curdate.day)
            activities.append(activity)

        return activities


    @classmethod
    def get_series_record_count(self, unit, start_date, end_date):
        cursor = connection.cursor()
        cursor.execute(self.get_generate_series_select_sql(unit, start_date, end_date))
        result = cursor.fetchall()
        return len(result)


    @classmethod
    def get_timeseries_sql(self, ts_prop, platform_list, verb = None):
        with_queries = self.get_with_queries(ts_prop, platform_list, verb)
        sql_list = []
        for platform in platform_list:
            sql = """(select 
                '%s'::text as platform,
                to_date(to_char(filled_dates.day, 'YYYY-MM-DD'), 'YYYY-MM-DD') date
                , coalesce(daily_counts_%s.smcount, filled_dates.blank_count) as counts
                from filled_dates
                left outer join daily_counts_%s on daily_counts_%s.day = filled_dates.day
                 order by filled_dates.day asc)
            """ % (platform, platform, platform, platform)
            sql_list.append(sql)

        if len(platform_list) > 1:
            sql = with_queries + ' union '.join(sql_list) + ' order by platform, date' 
        else:
            sql = with_queries + ' ' + ''.join(sql_list)

        return sql


    @classmethod
    def get_with_queries(self, ts_prop, platform_list, verb = None):
        with_clause_list = []
        daily_counts_list = []
        for platform in platform_list:
            daily_counts_list.append(self.get_daily_counts_with_queries(ts_prop, platform, verb = verb))

        return 'with ' + self.get_generate_series_with_queries(ts_prop, platform) \
                       + ',' + ', '.join(daily_counts_list)


    @classmethod
    def get_daily_counts_with_queries(self, ts_prop, platform, verb = None):
        ts_prop.platform = platform
        ts_prop.verb = verb
        clauses = self.get_clauses(ts_prop)
        # Create WITH queries for daily counts
        return """
            daily_counts_%s as (
                select 
                date_trunc('day', to_timestamp(substring(CAST(clatoolkit_learningrecord.datetimestamp as text) from 1 for 11), 'YYYY-MM-DD')) as day, 
                count(*) as smcount
                FROM clatoolkit_learningrecord
                WHERE clatoolkit_learningrecord.unit_id = %s 
                %s %s %s
                group by day
                order by day asc
            )
        """ % (platform, ts_prop.unit.id, 
                clauses['user_clause'], clauses['platform_clause'], clauses['verb_clause'])


    @classmethod
    def get_generate_series_with_queries(self, ts_prop, platform):
        generate_series_sql = self.get_generate_series_select_sql(ts_prop.unit, ts_prop.start_date, ts_prop.end_date)
        return " filled_dates as ( %s ) " % (generate_series_sql)
        

    @classmethod
    def get_generate_series_select_sql(self, unit, start_date, end_date):
        # more info on postgres timeseries
        # http://no0p.github.io/postgresql/2014/05/08/timeseries-tips-pg.html
        
        # Create WITH queries for generating series data
        start_clause = "(select start_date from clatoolkit_unitoffering where id = %s)" % (unit.id)
        end_clause = "(select end_date from clatoolkit_unitoffering where id = %s)" % (unit.id)

        if start_date is not None:
            # When start date param is larger than start date in unit profile 
            if Utility.compare_to(start_date, unit.start_date) == 1:
                start_clause = " '%s' " % start_date
            
        if end_date is not None:
            # When start date param is larger than start date in unit profile 
            if Utility.compare_to(end_date, unit.end_date) == -1:
                end_clause = " '%s' " % end_date
        
        return "SELECT generate_series( %s, %s, interval '1 day') as day, 0 as blank_count" \
                % (start_clause, end_clause)


    @classmethod
    def get_clauses(self, ts_prop):
        platformclause = ""
        if ts_prop.platform:
            platforms = ts_prop.platform.split(',')
            if len(platforms) == 1:
                if ts_prop.platform is not None and ts_prop.platform != "all":
                    platformclause = " and clatoolkit_learningrecord.platform = '%s' " % (ts_prop.platform)
            elif len(platforms) > 1:
                names = []
                for p in platforms:
                    names.append("'" + p + "'")

                platformclause = " and clatoolkit_learningrecord.platform in (%s) " % (', '.join(names))

        verb_clause = ""
        if ts_prop.verb is not None:
            verb_clause = " and clatoolkit_learningrecord.verb = '%s' " % (ts_prop.verb)
            
        user_clause = ""
        if ts_prop.user is not None:
            user_clause = " and clatoolkit_learningrecord.user_id = %s " % (ts_prop.user.id)

        orderby_clause = ' order by filled_dates.day asc'
        if ts_prop.order_by is not None:
            if ts_prop.order_by == self.STR_ORDER_BY_DATE:
                orderby_clause = ' order by filled_dates.day %s' % (ts_prop.order)
            # If other order by clause are required...
            # elif order_by != self.STR_ORDER_BY_DATE:
            #     pass
            else:
                # Default order by clause
                orderby_clause = ' order by filled_dates.day %s' % (ts_prop.order)

        return {
            'platform_clause': platformclause,
            'verb_clause': verb_clause,
            'user_clause': user_clause,
        }


    @classmethod
    def get_orderby(self, order_by_str):
        asc = 'asc'
        desc = 'desc'

        if order_by_str is None:
            # Default order
            return self.STR_ORDER_BY_DATE, asc

        orderby_list = order_by_str.split(',')
        for orderby in orderby_list:
            o = orderby.split('-')
            if len(o) == 1:
                if o[0] == self.STR_ORDER_BY_DATE:
                    return o[0], asc
                else:
                    # Default order
                    return self.STR_ORDER_BY_DATE, asc
            elif len(o) == 2:
                if o[1] == self.STR_ORDER_BY_DATE:
                    return o[1], desc
                else:
                    # Default order
                    return self.STR_ORDER_BY_DATE, asc

