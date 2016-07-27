# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('clatoolkit', '0008_auto_20160718_0614'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserTrelloCourseBoardMap',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_code', models.CharField(max_length=1000)),
                ('board_id', models.CharField(max_length=5000)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='trello_user_board_ids',
        ),
        migrations.AddField(
            model_name='unitoffering',
            name='attached_trello_boards',
            field=models.TextField(blank=True),
        ),
    ]
