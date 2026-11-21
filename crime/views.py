from django.shortcuts import render, redirect
from .models import CrimeReport
from django.conf import settings
def home(request):
    import pandas as pd

    df = pd.read_csv(str(settings.BASE_DIR)+"/crime_dataset_india.csv")

    print(df.head())
    print("Total records:", len(df))

    return render(request, 'crime/home.html')


def report_form(request):

    if request.method == 'POST':

        title = request.POST.get('title')
        description = request.POST.get('description')
        location = request.POST.get('location')
        date_reported = request.POST.get('date_reported')

        CrimeReport.objects.create(
            title=title,
            description=description,
            location=location,
            date_reported=date_reported
        )

        return redirect('home')

    return render(request, 'crime/report_form.html')
