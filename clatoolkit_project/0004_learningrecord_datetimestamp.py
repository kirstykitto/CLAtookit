# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clatoolkit', '0003_auto_20170119_0327'),
    ]

    operations = [
        migrations.AlterField(
            model_name='learningrecord',
            name='datetimestamp',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
