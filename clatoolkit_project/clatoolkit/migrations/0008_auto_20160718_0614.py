# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clatoolkit', '0007_offlineplatformauthtoken'),
    ]

    operations = [
        migrations.RenameField(
            model_name='userprofile',
            old_name='trello_user_id',
            new_name='trello_account_name',
        ),
    ]
