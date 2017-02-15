# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clatoolkit', '0001_squashed_0002_auto_20170206_0521'),
    ]

    operations = [
        migrations.AddField(
            model_name='unitoffering',
            name='co_analysis',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='unitoffering',
            name='sn_analysis',
            field=models.BooleanField(default=True),
        ),
    ]
