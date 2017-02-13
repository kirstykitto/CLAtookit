# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('clatoolkit', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='dashboardreflection',
            name='unit',
            field=models.ForeignKey(default=1, to='clatoolkit.UnitOffering'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='learningrecord',
            name='datetimestamp',
            field=models.DateTimeField(default=datetime.datetime(2017, 2, 6, 5, 21, 4, 225460, tzinfo=utc)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='unitoffering',
            name='end_date',
            field=models.DateField(default=datetime.datetime(2017, 2, 6, 5, 21, 8, 763640, tzinfo=utc)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='unitoffering',
            name='start_date',
            field=models.DateField(default=datetime.datetime(2017, 2, 6, 5, 21, 13, 373698, tzinfo=utc)),
            preserve_default=False,
        ),
    ]
