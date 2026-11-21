from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crime', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='crimereport',
            name='date_reported',
            field=models.DateTimeField(),
        ),
        migrations.AddField(
            model_name='crimereport',
            name='report_number',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='crimereport',
            name='date_of_occurrence',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='crimereport',
            name='time_of_occurrence',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='crimereport',
            name='city',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='crimereport',
            name='crime_code',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='crimereport',
            name='crime_description',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='crimereport',
            name='victim_age',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='crimereport',
            name='victim_gender',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='crimereport',
            name='weapon_used',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='crimereport',
            name='crime_domain',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='crimereport',
            name='police_deployed',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='crimereport',
            name='case_closed',
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='crimereport',
            name='date_case_closed',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
