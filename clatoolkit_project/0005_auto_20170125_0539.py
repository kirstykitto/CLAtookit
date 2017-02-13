# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('clatoolkit', '0004_learningrecord_datetimestamp'),
    ]

    operations = [
        migrations.AlterField(
            model_name='learningrecord',
            name='datetimestamp',
            field=models.DateTimeField(default=datetime.datetime(2017, 1, 25, 5, 39, 21, 265039, tzinfo=utc), auto_now_add=True),
            preserve_default=False,
        ),
    ]
