# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clatoolkit', '0010_delete_oauthflowtemp'),
    ]

    operations = [
        migrations.CreateModel(
            name='OauthFlowTemp',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('googleid', models.CharField(max_length=1000)),
                ('platform', models.CharField(max_length=1000, blank=True)),
                ('course_code', models.CharField(max_length=1000, blank=True)),
                ('transferdata', models.CharField(max_length=1000, blank=True)),
            ],
        ),
    ]
