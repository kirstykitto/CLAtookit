# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clatoolkit', '0014_classification_userclassification'),
    ]

    operations = [
        migrations.AddField(
            model_name='userclassification',
            name='trained',
            field=models.BooleanField(default=False),
        ),
    ]
