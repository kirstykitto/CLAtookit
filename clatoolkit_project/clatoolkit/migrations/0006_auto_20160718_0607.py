# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clatoolkit', '0005_auto_20160717_0326'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='offlineplatformauthtoken',
            name='user',
        ),
        migrations.DeleteModel(
            name='OfflinePlatformAuthToken',
        ),
    ]
