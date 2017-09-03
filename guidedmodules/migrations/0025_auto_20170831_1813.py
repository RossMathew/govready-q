# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-08-31 18:13
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('guidedmodules', '0024_taskanswerhistory_reviewed'),
    ]

    operations = [
        migrations.AlterField(
            model_name='module',
            name='source',
            field=models.ForeignKey(help_text='The source of this module definition.', on_delete=django.db.models.deletion.CASCADE, related_name='modules', to='guidedmodules.ModuleSource'),
        ),
    ]