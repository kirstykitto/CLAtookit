# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clatoolkit', '0005_auto_20170125_0539'),
    ]

    operations = [
        migrations.AlterField(
            model_name='learningrecord',
            name='datetimestamp',
            field=models.DateTimeField(),
        ),
    ]
