from django.db import models
from django.utils.text import slugify



class CrimeReport(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=200)
    date_reported = models.DateTimeField()
    analysis = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    report_number = models.IntegerField(blank=True, null=True)
    date_of_occurrence = models.DateTimeField(blank=True, null=True)
    time_of_occurrence = models.DateTimeField(blank=True, null=True)
    city = models.CharField(max_length=200, blank=True)
    crime_code = models.IntegerField(blank=True, null=True)
    crime_description = models.TextField(blank=True)
    victim_age = models.IntegerField(blank=True, null=True)
    victim_gender = models.CharField(max_length=50, blank=True)
    weapon_used = models.CharField(max_length=200, blank=True)
    crime_domain = models.CharField(max_length=200, blank=True)
    police_deployed = models.IntegerField(blank=True, null=True)
    case_closed = models.BooleanField(blank=True, null=True)
    date_case_closed = models.DateTimeField(blank=True, null=True)

    def get_url_slug(self):
        return f'{slugify(self.title) or "report"}-{self.pk}'

    def __str__(self):
        return self.title