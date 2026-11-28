import logging
import os

from google import genai
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone
from .models import CrimeReport


logger = logging.getLogger(__name__)
ANALYSIS_TIMEOUT_SECONDS = 30


class GeminiAPIError(Exception):
    pass


def generate_crime_analysis(title, description, location, date_reported):
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise GeminiAPIError('The Gemini API key is not configured.')

    prompt = (
        'Analyze the following reported incident for clarity and review. '
        'Summarize only the provided facts, identify information that is '
        'missing or unclear, and suggest neutral follow-up questions. Do not '
        'infer guilt, identify a suspect, or present speculation as fact. '
        'This is an informational summary, not a legal conclusion.\n\n'
        f'Title: {title}\n'
        f'Description: {description}\n'
        f'Location: {location}\n'
        f'Date reported: {date_reported}'
    )

    try:
        client = genai.Client(api_key=api_key)
        interaction = client.interactions.create(
            model='gemini-3.8-flash',
            input=prompt,
            timeout=ANALYSIS_TIMEOUT_SECONDS,
        )
    except TimeoutError as error:
        raise GeminiAPIError(
            'Gemini analysis timed out after '
            f'{ANALYSIS_TIMEOUT_SECONDS} seconds. Please try again.'
        ) from error
    except genai.errors.APIError as error:
        raise GeminiAPIError(
            f'Gemini API returned HTTP {error.code}: '
            f'{error.message or "Unknown API error."}'
        ) from error

    analysis = interaction.output_text
    if not isinstance(analysis, str) or not analysis.strip():
        raise GeminiAPIError('Gemini returned an empty analysis.')
    return analysis.strip()


def home(request):
    return render(request, 'crime/home.html')


def reports(request):
    search_query = request.GET.get('q', '').strip()
    city_filter = request.GET.get('city', '').strip()
    case_status = request.GET.get('case_status', '').strip()

    report_list = CrimeReport.objects.all()

    if search_query:
        report_list = report_list.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(location__icontains=search_query)
            | Q(city__icontains=search_query)
            | Q(crime_description__icontains=search_query)
            | Q(weapon_used__icontains=search_query)
            | Q(crime_domain__icontains=search_query)
        )

    if city_filter:
        report_list = report_list.filter(city=city_filter)

    if case_status == 'open':
        report_list = report_list.filter(case_closed=False)
    elif case_status == 'closed':
        report_list = report_list.filter(case_closed=True)
    elif case_status == 'unknown':
        report_list = report_list.filter(case_closed__isnull=True)
    else:
        case_status = ''

    report_list = report_list.order_by('-date_reported', '-pk')
    paginator = Paginator(report_list, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    def page_url(page_number):
        query_params = request.GET.copy()
        query_params['page'] = page_number
        return f'?{query_params.urlencode()}'

    return render(request, 'crime/report.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'city_filter': city_filter,
        'case_status': case_status,
        'cities': CrimeReport.objects.exclude(city='').values_list(
            'city', flat=True
        ).distinct().order_by('city'),
        'previous_url': page_url(page_obj.previous_page_number())
        if page_obj.has_previous() else None,
        'next_url': page_url(page_obj.next_page_number())
        if page_obj.has_next() else None,
    })


def report_form(request):

    if request.method == 'POST':

        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        location = request.POST.get('location', '').strip()
        date_reported = request.POST.get('date_reported', '').strip()
        try:
            parsed_date_reported = datetime.strptime(
                date_reported, '%Y-%m-%d'
            )
        except ValueError:
            return render(request, 'crime/report_form.html', {
                'form_data': request.POST,
                'date_error': 'Enter a valid date.',
            })

        if parsed_date_reported.date() > timezone.localdate():
            return render(request, 'crime/report_form.html', {
                'form_data': request.POST,
                'date_error': 'Date reported cannot be in the future.',
            })

        parsed_date_reported = timezone.make_aware(parsed_date_reported)

        report = CrimeReport.objects.create(
            title=title,
            description=description,
            location=location,
            date_reported=parsed_date_reported
        )

        return redirect('report_detail', slug=report.get_url_slug())

    return render(request, 'crime/report_form.html')


def report_detail(request, slug):
    try:
        report_id = int(slug.rsplit('-', 1)[1])
    except (IndexError, ValueError) as error:
        raise Http404 from error

    report = get_object_or_404(CrimeReport, pk=report_id)
    if slug != report.get_url_slug():
        return redirect('report_detail', slug=report.get_url_slug())

    analysis_error = None

    if request.method == 'POST':
        try:
            report.analysis = generate_crime_analysis(
                report.title,
                report.description,
                report.location,
                report.date_reported,
            )
            report.save(update_fields=['analysis'])
        except GeminiAPIError as error:
            logger.warning('Crime analysis unavailable: %s', error)
            analysis_error = (
                'Gemini could not analyze this report within 30 seconds or '
                'is temporarily unavailable. Please try again.'
            )

    return render(request, 'crime/report_detail.html', {
        'report': report,
        'analysis_error': analysis_error,
    })
