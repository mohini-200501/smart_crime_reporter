import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q
from .models import CrimeReport


logger = logging.getLogger(__name__)


class GeminiAPIError(Exception):
    pass


def generate_crime_analysis(title, description, location, date_reported):
    api_key = os.getenv('GEMIINI_API_KEY')
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
    request = Request(
        'https://generativelanguage.googleapis.com/v1beta/models/'
        'gemini-2.5-flash:generateContent',
        data=json.dumps({
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': 0.2},
        }).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'x-goog-api-key': api_key,
        },
        method='POST',
    )

    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read())
    except HTTPError as error:
        raise GeminiAPIError(
            f'Gemini returned HTTP status {error.code}.'
        ) from error
    except (URLError, TimeoutError) as error:
        raise GeminiAPIError('Gemini could not be reached.') from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise GeminiAPIError('Gemini returned an invalid response.') from error

    if not isinstance(result, dict):
        raise GeminiAPIError('Gemini returned an invalid response.')

    candidates = result.get('candidates')
    if not isinstance(candidates, list) or not candidates:
        raise GeminiAPIError('Gemini did not return an analysis.')

    candidate = candidates[0]
    content = candidate.get('content') if isinstance(candidate, dict) else None
    parts = content.get('parts') if isinstance(content, dict) else None
    if not isinstance(parts, list):
        raise GeminiAPIError('Gemini returned an invalid response.')

    analysis = '\n'.join(
        part['text'] for part in parts
        if isinstance(part, dict) and isinstance(part.get('text'), str)
    ).strip()
    if not analysis:
        raise GeminiAPIError('Gemini returned an empty analysis.')
    return analysis


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

        report = CrimeReport.objects.create(
            title=title,
            description=description,
            location=location,
            date_reported=date_reported
        )

        try:
            analysis = generate_crime_analysis(
                title, description, location, date_reported
            )
            analysis_error = None
        except GeminiAPIError as error:
            logger.warning('Crime analysis unavailable: %s', error)
            analysis = None
            analysis_error = (
                'Your report was saved, but Gemini could not analyze it '
                'right now. Please try again later.'
            )

        return render(request, 'crime/report_analysis.html', {
            'report': report,
            'analysis': analysis,
            'analysis_error': analysis_error,
        })

    return render(request, 'crime/report_form.html')
