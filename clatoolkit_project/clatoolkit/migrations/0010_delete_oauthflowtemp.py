# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clatoolkit', '0009_auto_20160718_0929'),
    ]

    operations = [
        migrations.DeleteModel(
            name='OauthFlowTemp',
        ),
    ]
