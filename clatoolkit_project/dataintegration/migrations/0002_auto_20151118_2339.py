# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dataintegration', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='comment',
            name='parentUsername',
            field=models.CharField(max_length=1000, blank=True),
        ),
        migrations.AlterField(
            model_name='comment',
            name='authorDispName',
            field=models.CharField(max_length=1000),
        ),
    ]
