# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clatoolkit', '0002_auto_20160717_0140'),
    ]

    operations = [
        migrations.AddField(
            model_name='unitoffering',
            name='github_urls',
            field=models.TextField(blank=True),
        ),
    ]
