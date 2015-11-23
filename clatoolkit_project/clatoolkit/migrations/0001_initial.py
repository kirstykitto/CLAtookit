# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_pgjson.fields
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AccessLog',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('url', models.CharField(max_length=10000)),
                ('userid', models.CharField(max_length=5000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='ApiCredentials',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('platform', models.CharField(max_length=5000)),
                ('credentials_json', django_pgjson.fields.JsonField()),
            ],
        ),
        migrations.CreateModel(
            name='CachedContent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('htmltable', models.TextField()),
                ('activitytable', models.TextField(blank=True)),
                ('course_code', models.CharField(max_length=5000)),
                ('platform', models.CharField(max_length=5000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Classification',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('classification', models.CharField(max_length=1000)),
                ('classifier', models.CharField(max_length=1000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='DashboardReflection',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('username', models.CharField(max_length=5000)),
                ('strategy', models.TextField()),
                ('rating', models.CharField(default=b'Satisfied', max_length=50, choices=[(b'Happy', b'Happy'), (b'Satisfied', b'Satisfied'), (b'Unhappy', b'Unhappy')])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='GroupMap',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_code', models.CharField(max_length=5000)),
                ('groupId', models.CharField(max_length=5000)),
            ],
        ),
        migrations.CreateModel(
            name='LearningRecord',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('xapi', django_pgjson.fields.JsonField()),
                ('course_code', models.CharField(max_length=5000)),
                ('platform', models.CharField(max_length=5000)),
                ('verb', models.CharField(max_length=5000)),
                ('username', models.CharField(max_length=5000, blank=True)),
                ('platformid', models.CharField(max_length=5000, blank=True)),
                ('platformparentid', models.CharField(max_length=5000, blank=True)),
                ('parentusername', models.CharField(max_length=5000, blank=True)),
                ('message', models.TextField(blank=True)),
                ('datetimestamp', models.DateTimeField(null=True, blank=True)),
                ('senttolrs', models.CharField(max_length=5000, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='SocialRelationship',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_code', models.CharField(max_length=5000)),
                ('platform', models.CharField(max_length=5000)),
                ('verb', models.CharField(max_length=5000)),
                ('fromusername', models.CharField(max_length=5000, blank=True)),
                ('tousername', models.CharField(max_length=5000, blank=True)),
                ('platformid', models.CharField(max_length=5000, blank=True)),
                ('message', models.TextField()),
                ('datetimestamp', models.DateTimeField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='UnitOffering',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', models.CharField(max_length=5000)),
                ('name', models.CharField(max_length=5000)),
                ('semester', models.CharField(max_length=5000)),
                ('description', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('enabled', models.BooleanField(default=False)),
                ('event', models.BooleanField(default=False)),
                ('twitter_hashtags', models.TextField()),
                ('google_groups', models.TextField(blank=True)),
                ('facebook_groups', models.TextField(blank=True)),
                ('forum_urls', models.TextField(blank=True)),
                ('youtube_channelIds', models.TextField(blank=True)),
                ('ll_endpoint', models.CharField(max_length=60, blank=True)),
                ('ll_username', models.CharField(max_length=60, blank=True)),
                ('ll_password', models.CharField(max_length=60, blank=True)),
                ('users', models.ManyToManyField(related_name='usersinunitoffering', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='UserClassification',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('username', models.CharField(max_length=5000)),
                ('isclassificationcorrect', models.BooleanField()),
                ('userreclassification', models.CharField(max_length=1000)),
                ('feedback', models.TextField(blank=True)),
                ('feature', models.TextField(blank=True)),
                ('trained', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('classification', models.ForeignKey(to='clatoolkit.Classification')),
            ],
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('role', models.CharField(default=b'Student', max_length=100, choices=[(b'Staff', b'Staff'), (b'Student', b'Student'), (b'Visitor', b'Visitor')])),
                ('fb_id', models.CharField(max_length=30, blank=True)),
                ('twitter_id', models.CharField(max_length=30, blank=True)),
                ('forum_id', models.CharField(max_length=500, blank=True)),
                ('google_account_name', models.CharField(max_length=255, blank=True)),
                ('user', models.OneToOneField(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='groupmap',
            name='userId',
            field=models.ForeignKey(to='clatoolkit.UserProfile'),
        ),
        migrations.AddField(
            model_name='classification',
            name='xapistatement',
            field=models.ForeignKey(to='clatoolkit.LearningRecord'),
        ),
    ]
