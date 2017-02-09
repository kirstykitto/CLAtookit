# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_pgjson.fields
import django.utils.timezone
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
                ('platform_uid', models.CharField(max_length=5000)),
                ('credentials_json', django_pgjson.fields.JsonField()),
            ],
        ),
        migrations.CreateModel(
            name='CachedContent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('htmltable', models.TextField()),
                ('activitytable', models.TextField(blank=True)),
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
                ('groupId', models.IntegerField()),
                ('userId', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='LearningRecord',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('xapi', django_pgjson.fields.JsonField()),
                ('platform', models.CharField(max_length=5000)),
                ('verb', models.CharField(max_length=5000)),
                ('platformid', models.CharField(max_length=5000, blank=True)),
                ('platformparentid', models.CharField(max_length=5000, blank=True)),
                ('parent_user_external', models.CharField(max_length=5000, null=True, blank=True)),
                ('message', models.TextField(blank=True)),
                ('datetimestamp', models.DateTimeField(default=django.utils.timezone.now)),
                ('senttolrs', models.CharField(max_length=5000, blank=True)),
                ('parent_user', models.ForeignKey(related_name='parent_user', to=settings.AUTH_USER_MODEL, null=True)),
            ],
        ),
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
        migrations.CreateModel(
            name='OfflinePlatformAuthToken',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('user_smid', models.CharField(max_length=1000)),
                ('token', models.CharField(max_length=1000)),
                ('platform', models.CharField(max_length=1000)),
            ],
        ),
        migrations.CreateModel(
            name='SocialRelationship',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('platform', models.CharField(max_length=5000)),
                ('verb', models.CharField(max_length=5000)),
                ('to_external_user', models.CharField(max_length=5000, null=True, blank=True)),
                ('platformid', models.CharField(max_length=5000, blank=True)),
                ('message', models.TextField()),
                ('datetimestamp', models.DateTimeField(blank=True)),
                ('from_user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
                ('to_user', models.ForeignKey(related_name='to_user', to=settings.AUTH_USER_MODEL, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='UnitOffering',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', models.CharField(unique=True, max_length=5000, verbose_name=b'Unit Code')),
                ('name', models.CharField(max_length=5000, verbose_name=b'Unit Name')),
                ('semester', models.CharField(max_length=5000)),
                ('description', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('enabled', models.BooleanField(default=True)),
                ('event', models.BooleanField(default=False)),
                ('enable_coi_classifier', models.BooleanField(default=False)),
                ('twitter_hashtags', models.TextField(verbose_name=b'Twitter Hashtags')),
                ('google_groups', models.TextField(verbose_name=b'Google Groups', blank=True)),
                ('facebook_groups', models.TextField(verbose_name=b'Facebook Groups', blank=True)),
                ('forum_urls', models.TextField(verbose_name=b'Forum URLs', blank=True)),
                ('youtube_channelIds', models.TextField(verbose_name=b'Youtube Channels', blank=True)),
                ('diigo_tags', models.TextField(verbose_name=b'Diigo Tags', blank=True)),
                ('blogmember_urls', models.TextField(verbose_name=b'Blog Member URLs', blank=True)),
                ('github_urls', models.TextField(verbose_name=b'GitHub Repos', blank=True)),
                ('attached_trello_boards', models.TextField(verbose_name=b'Trello Boards', blank=True)),
                ('coi_platforms', models.TextField(blank=True)),
                ('ll_endpoint', models.CharField(max_length=60, blank=True)),
                ('ll_username', models.CharField(max_length=60, blank=True)),
                ('ll_password', models.CharField(max_length=60, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='UnitOfferingMembership',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('admin', models.BooleanField(default=False)),
                ('unit', models.ForeignKey(to='clatoolkit.UnitOffering')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
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
                ('diigo_username', models.CharField(max_length=255, blank=True)),
                ('blog_id', models.CharField(max_length=255, blank=True)),
                ('github_account_name', models.CharField(max_length=255, blank=True)),
                ('trello_account_name', models.CharField(max_length=255, blank=True)),
                ('user', models.OneToOneField(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='UserTrelloCourseBoardMap',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_code', models.CharField(max_length=1000)),
                ('board_id', models.CharField(max_length=5000)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='unitoffering',
            name='users',
            field=models.ManyToManyField(related_name='usersinunitoffering', through='clatoolkit.UnitOfferingMembership', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='socialrelationship',
            name='unit',
            field=models.ForeignKey(to='clatoolkit.UnitOffering'),
        ),
        migrations.AddField(
            model_name='learningrecord',
            name='unit',
            field=models.ForeignKey(to='clatoolkit.UnitOffering'),
        ),
        migrations.AddField(
            model_name='learningrecord',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='classification',
            name='xapistatement',
            field=models.ForeignKey(to='clatoolkit.LearningRecord'),
        ),
        migrations.AddField(
            model_name='cachedcontent',
            name='unit',
            field=models.ForeignKey(to='clatoolkit.UnitOffering'),
        ),
    ]
