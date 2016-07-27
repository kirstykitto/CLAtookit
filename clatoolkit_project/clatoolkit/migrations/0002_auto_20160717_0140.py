# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clatoolkit', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='github_account_name',
            field=models.CharField(max_length=255, blank=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='trello_user_board_ids',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='trello_user_id',
            field=models.CharField(max_length=255, blank=True),
        ),
    ]
