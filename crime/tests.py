import os
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone
from google import genai

from .models import CrimeReport
from .views import GeminiAPIError, generate_crime_analysis


class GeminiClientTests(TestCase):
    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'})
    @patch('crime.views.genai.Client')
    def test_analysis_uses_gemini_sdk(self, client_factory):
        client = client_factory.return_value
        client.interactions.create.return_value.output_text = 'Review summary'

        analysis = generate_crime_analysis(
            'Theft', 'A phone was stolen.', 'Mumbai', '2026-11-26'
        )

        self.assertEqual(analysis, 'Review summary')
        client_factory.assert_called_once_with(api_key='test-key')
        request = client.interactions.create.call_args.kwargs
        self.assertEqual(request['model'], 'gemini-3.8-flash')
        self.assertEqual(request['timeout'], 30)
        self.assertIn('A phone was stolen.', request['input'])

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'})
    @patch('crime.views.genai.Client')
    def test_analysis_timeout_is_reported_clearly(self, client_factory):
        client_factory.return_value.interactions.create.side_effect = TimeoutError

        with self.assertRaisesRegex(GeminiAPIError, 'timed out after 30 seconds'):
            generate_crime_analysis(
                'Theft', 'A phone was stolen.', 'Mumbai', '2026-11-26'
            )

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'})
    @patch('crime.views.genai.Client')
    def test_sdk_api_error_is_reported_with_details(self, client_factory):
        client_factory.return_value.interactions.create.side_effect = (
            genai.errors.ClientError(
                404, {'error': {'message': 'Model not found'}}
            )
        )

        with self.assertRaisesRegex(
            GeminiAPIError, 'HTTP 404: Model not found'
        ):
            generate_crime_analysis(
                'Theft', 'A phone was stolen.', 'Mumbai', '2026-11-26'
            )


class ReportsViewTests(TestCase):
    def create_report(self, title, **kwargs):
        return CrimeReport.objects.create(
            title=title,
            description=kwargs.pop('description', 'Incident details'),
            location=kwargs.pop('location', 'Unknown'),
            date_reported=timezone.now(),
            **kwargs,
        )

    def test_search_and_filters_can_be_combined(self):
        matching_report = self.create_report(
            'Incident report',
            crime_description='Stolen smartphone',
            city='Mumbai',
            case_closed=False,
        )
        self.create_report(
            'Another report',
            crime_description='Stolen smartphone',
            city='Delhi',
            case_closed=False,
        )
        self.create_report(
            'Closed report',
            crime_description='Stolen smartphone',
            city='Mumbai',
            case_closed=True,
        )

        response = self.client.get('/reports/', {
            'q': 'smartphone',
            'city': 'Mumbai',
            'case_status': 'open',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['page_obj'].object_list), [matching_report])

    def test_pagination_preserves_active_search_filter(self):
        for index in range(12):
            self.create_report(f'Report {index}', description='Searchable report')

        response = self.client.get('/reports/', {'q': 'Searchable'})

        self.assertEqual(response.context['page_obj'].paginator.count, 12)
        self.assertEqual(len(response.context['page_obj'].object_list), 10)
        self.assertIn('q=Searchable', response.context['next_url'])

        next_page = self.client.get(f"/reports/{response.context['next_url']}")
        self.assertEqual(next_page.context['page_obj'].number, 2)
        self.assertEqual(len(next_page.context['page_obj'].object_list), 2)


class ReportFormGeminiTests(TestCase):
    def test_post_saves_report_without_running_analysis(self):
        with patch(
            'crime.views.generate_crime_analysis',
            return_value='Review summary',
        ) as analyze:
            response = self.client.post('/report/', {
                'title': 'Theft',
                'description': 'A phone was stolen.',
                'location': 'Mumbai',
                'date_reported': '2026-11-26',
            })

        report = CrimeReport.objects.get()
        self.assertRedirects(response, f'/report/{report.get_url_slug()}/')
        self.assertEqual(CrimeReport.objects.count(), 1)
        self.assertEqual(report.analysis, '')
        analyze.assert_not_called()

    def test_detail_page_has_separate_analyze_action(self):
        report = CrimeReport.objects.create(
            title='Theft',
            description='A phone was stolen.',
            location='Mumbai',
            date_reported=timezone.now(),
        )

        with patch('crime.views.generate_crime_analysis') as analyze:
            response = self.client.get(f'/report/{report.get_url_slug()}/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Analyze report')
        analyze.assert_not_called()

    def test_analyze_action_persists_result_on_report_detail(self):
        report = CrimeReport.objects.create(
            title='Theft',
            description='A phone was stolen.',
            location='Mumbai',
            date_reported=timezone.now(),
        )

        with patch(
            'crime.views.generate_crime_analysis',
            return_value='Review summary',
        ) as analyze:
            response = self.client.post(f'/report/{report.get_url_slug()}/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Review summary')
        report.refresh_from_db()
        self.assertEqual(report.analysis, 'Review summary')
        analyze.assert_called_once_with(
            'Theft', 'A phone was stolen.', 'Mumbai', report.date_reported
        )

    def test_gemini_failure_keeps_report_and_shows_error(self):
        report = CrimeReport.objects.create(
            title='Theft',
            description='A phone was stolen.',
            location='Mumbai',
            date_reported=timezone.now(),
        )
        with patch(
            'crime.views.generate_crime_analysis',
            side_effect=GeminiAPIError('Gemini is unavailable'),
        ):
            response = self.client.post(f'/report/{report.get_url_slug()}/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gemini could not analyze this report')
        self.assertEqual(CrimeReport.objects.count(), 1)
