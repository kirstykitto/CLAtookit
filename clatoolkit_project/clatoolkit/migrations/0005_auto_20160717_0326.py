# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clatoolkit', '0004_auto_20160717_0142'),
    ]

    operations = [
        migrations.RenameField(
            model_name='apicredentials',
            old_name='platform',
            new_name='platform_uid',
        ),
    ]
