from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .models import CrimeReport
from .views import GeminiAPIError


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
