# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clatoolkit', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='dashboardreflection',
            name='unit',
            field=models.ForeignKey(default=5, to='clatoolkit.UnitOffering'),
            preserve_default=False,
        ),
    ]
