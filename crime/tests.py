import os
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from .models import CrimeReport
from .views import GeminiAPIError, generate_crime_analysis


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
    def test_generate_analysis_uses_standard_gemini_api_key(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = (
            b'{"candidates":[{"content":{"parts":[{"text":"Review summary"}]}}]}'
        )

        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}, clear=True):
            with patch('crime.views.urlopen', return_value=response) as urlopen:
                analysis = generate_crime_analysis(
                    'Theft', 'Phone stolen.', 'Mumbai', '2026-11-26'
                )

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header('X-goog-api-key'), 'test-key')
        self.assertEqual(analysis, 'Review summary')

    def test_future_reported_date_is_rejected(self):
        future_date = (timezone.localdate() + timedelta(days=1)).isoformat()

        response = self.client.post('/report/', {
            'title': 'Theft',
            'description': 'A phone was stolen.',
            'location': 'Mumbai',
            'date_reported': future_date,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Date reported cannot be in the future.')
        self.assertContains(response, f'max="{timezone.localdate().isoformat()}"')
        self.assertEqual(CrimeReport.objects.count(), 0)

    def test_post_saves_report_and_displays_gemini_analysis(self):
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

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Review summary')
        self.assertContains(response, 'Nov 26, 2026')
        self.assertEqual(CrimeReport.objects.count(), 1)
        analyze.assert_called_once_with(
            'Theft', 'A phone was stolen.', 'Mumbai', '2026-11-26'
        )

    def test_gemini_failure_keeps_saved_report_and_shows_error(self):
        with patch(
            'crime.views.generate_crime_analysis',
            side_effect=GeminiAPIError('Gemini is unavailable'),
        ):
            response = self.client.post('/report/', {
                'title': 'Theft',
                'description': 'A phone was stolen.',
                'location': 'Mumbai',
                'date_reported': '2026-11-26',
            })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your report was saved')
        self.assertEqual(CrimeReport.objects.count(), 1)
