# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('clatoolkit', '0002_dashboardreflection_unit'),
    ]

    operations = [
        migrations.AddField(
            model_name='unitoffering',
            name='end_date',
            field=models.DateField(default=datetime.datetime(2017, 1, 19, 3, 27, 46, 545747, tzinfo=utc)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='unitoffering',
            name='start_date',
            field=models.DateField(default=datetime.datetime(2017, 1, 19, 3, 27, 52, 5056, tzinfo=utc)),
            preserve_default=False,
        ),
    ]
