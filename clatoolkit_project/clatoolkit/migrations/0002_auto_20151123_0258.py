# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clatoolkit', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='groupmap',
            name='groupId',
            field=models.IntegerField(max_length=5000),
        ),
    ]
