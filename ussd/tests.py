from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
from .models import FaultReport


class USSDReportFaultFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('ussd_callback')
        self.phone_number = '+2348012345678'
        self.session_id = 'test-session-12345'
        self.service_code = '*384*123#'

    def _post(self, text):
        return self.client.post(self.url, data={
            'sessionId': self.session_id,
            'serviceCode': self.service_code,
            'phoneNumber': self.phone_number,
            'text': text,
        })

    def test_get_request_rejected(self):
        """GET request to /ussd/ must be rejected with 405 Method Not Allowed."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_1_initial_menu(self):
        """Initial request text='' returns welcome and main menu."""
        response = self._post('')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertTrue(content.startswith('CON'))
        self.assertIn('Welcome to FactoryPulse', content)
        self.assertIn('1. Report Fault', content)
        self.assertIn('2. Check Machine', content)
        self.assertIn('3. My Reports', content)

    def test_2_report_fault_selection(self):
        """Selecting 1 shows Select Machine menu."""
        response = self._post('1')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertTrue(content.startswith('CON Select Machine'))
        self.assertIn('1. Generator', content)
        self.assertIn('2. Packaging Machine', content)
        self.assertIn('3. Milling Machine', content)

    def test_3_machine_selection(self):
        """Selecting machine 1 (Generator) shows problem selection menu."""
        response = self._post('1*1')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertTrue(content.startswith('CON What is the problem?'))
        self.assertIn('1. Not working', content)
        self.assertIn('2. Overheating', content)
        self.assertIn('3. Making noise', content)
        self.assertIn('4. Other', content)

    def test_4_problem_selection(self):
        """Selecting problem 2 (Overheating) shows severity selection menu."""
        response = self._post('1*1*2')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertTrue(content.startswith('CON Select severity'))
        self.assertIn('1. Low', content)
        self.assertIn('2. Medium', content)
        self.assertIn('3. High', content)
        self.assertIn('4. Critical', content)

    def test_5_severity_selection(self):
        """Selecting severity 3 (High) shows confirmation summary screen."""
        response = self._post('1*1*2*3')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertTrue(content.startswith('CON Report Summary'))
        self.assertIn('Machine: Generator', content)
        self.assertIn('Problem: Overheating', content)
        self.assertIn('Severity: High', content)
        self.assertIn('1. Submit', content)
        self.assertIn('2. Cancel', content)

    def test_6_and_7_confirmation_and_successful_fault_creation(self):
        """Submitting at confirmation creates FaultReport in DB and returns END with Fault ID."""
        self.assertEqual(FaultReport.objects.count(), 0)

        response = self._post('1*1*2*3*1')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertTrue(content.startswith('END Fault report submitted successfully.'))
        self.assertIn('Fault ID: #', content)

        # Verify DB record
        self.assertEqual(FaultReport.objects.count(), 1)
        fault = FaultReport.objects.first()
        self.assertEqual(fault.phone_number, self.phone_number)
        self.assertEqual(fault.machine, 'Generator')
        self.assertEqual(fault.problem, 'Overheating')
        self.assertEqual(fault.severity, 'High')
        self.assertEqual(fault.status, FaultReport.STATUS_OPEN)
        self.assertIn(f"Fault ID: #{fault.id}", content)

    def test_8_invalid_machine_selection(self):
        """Invalid machine selection returns Invalid option with machine menu."""
        response = self._post('1*9')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertTrue(content.startswith('CON Invalid option.'))
        self.assertIn('Select Machine', content)
        self.assertIn('1. Generator', content)

    def test_invalid_problem_selection(self):
        """Invalid problem selection returns Invalid option with problem menu."""
        response = self._post('1*1*9')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertTrue(content.startswith('CON Invalid option.'))
        self.assertIn('What is the problem?', content)
        self.assertIn('1. Not working', content)

    def test_9_invalid_severity_selection(self):
        """Invalid severity selection returns Invalid option with severity menu."""
        response = self._post('1*1*2*9')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertTrue(content.startswith('CON Invalid option.'))
        self.assertIn('Select severity', content)
        self.assertIn('1. Low', content)

    def test_invalid_confirmation_selection(self):
        """Invalid confirmation choice returns Invalid option with confirmation menu."""
        response = self._post('1*1*2*3*9')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertTrue(content.startswith('CON Invalid option.'))
        self.assertIn('Report Summary', content)
        self.assertIn('1. Submit', content)

    def test_10_cancellation(self):
        """Sending 0 at any stage or 2 at confirmation cancels the fault report."""
        # Cancel at initial menu
        res1 = self._post('0')
        self.assertEqual(res1.content.decode('utf-8'), 'END Fault report cancelled.')

        # Cancel after entering Report Fault
        res2 = self._post('1*0')
        self.assertEqual(res2.content.decode('utf-8'), 'END Fault report cancelled.')

        # Cancel at confirmation screen using option 2
        res3 = self._post('1*1*2*3*2')
        self.assertEqual(res3.content.decode('utf-8'), 'END Fault report cancelled.')

        # Verify no record created
        self.assertEqual(FaultReport.objects.count(), 0)

    def test_11_other_problem_flow(self):
        """Selecting 4. Other prompts for custom description and stores it."""
        # Step: Select 4 (Other)
        res_other = self._post('1*2*4')
        content_other = res_other.content.decode('utf-8')
        self.assertEqual(content_other, 'CON Describe the problem:')

        # Step: User types custom problem description
        res_desc = self._post('1*2*4*Conveyor belt broken')
        content_desc = res_desc.content.decode('utf-8')
        self.assertTrue(content_desc.startswith('CON Select severity'))

        # Step: Select severity 4 (Critical)
        res_sev = self._post('1*2*4*Conveyor belt broken*4')
        content_sev = res_sev.content.decode('utf-8')
        self.assertTrue(content_sev.startswith('CON Report Summary'))
        self.assertIn('Machine: Packaging Machine', content_sev)
        self.assertIn('Problem: Conveyor belt broken', content_sev)
        self.assertIn('Severity: Critical', content_sev)

        # Step: Submit
        res_submit = self._post('1*2*4*Conveyor belt broken*4*1')
        content_submit = res_submit.content.decode('utf-8')
        self.assertTrue(content_submit.startswith('END Fault report submitted successfully.'))

        # Check DB
        fault = FaultReport.objects.filter(problem='Conveyor belt broken').first()
        self.assertIsNotNone(fault)
        self.assertEqual(fault.machine, 'Packaging Machine')
        self.assertEqual(fault.severity, 'Critical')
        self.assertEqual(fault.status, 'OPEN')

    def test_12_fault_status_starts_as_open(self):
        """New fault report record default status is strictly OPEN."""
        self._post('1*3*1*1*1')
        fault = FaultReport.objects.latest('id')
        self.assertEqual(fault.status, 'OPEN')

    def test_no_credentials_exposed(self):
        """Ensure responses do not leak sensitive credentials."""
        response = self._post('')
        content = response.content.decode('utf-8')
        if hasattr(settings, 'SECRET_KEY') and settings.SECRET_KEY:
            self.assertNotIn(settings.SECRET_KEY, content)
        if hasattr(settings, 'AFRICASTALKING_API_KEY') and settings.AFRICASTALKING_API_KEY:
            self.assertNotIn(settings.AFRICASTALKING_API_KEY, content)


class PublicLandingPageTests(TestCase):
    """
    Tests for the public landing page at route '/'.
    """

    def setUp(self):
        self.client = Client()
        self.landing_url = '/'

    def test_landing_page_status_and_template(self):
        """GET / should return 200 and render landing.html."""
        response = self.client.get(self.landing_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ussd/landing.html')

    def test_landing_page_content_and_brand(self):
        """Ensure all key required text, headlines, and Africa's Talking integration sections exist."""
        response = self.client.get(self.landing_url)
        content = response.content.decode('utf-8')

        # Brand & Hero
        self.assertIn('FactoryPulse', content)
        self.assertIn('Smarter Fault Reporting.', content)
        self.assertIn('Faster Maintenance.', content)
        self.assertIn("Built for Manufacturing", content)
        self.assertIn("Powered by Africa's Talking", content)

        # Africa's Talking section
        self.assertIn("Built Around Africa's Talking", content)
        self.assertIn('USSD', content)
        self.assertIn('SMS', content)
        self.assertIn('Webhooks', content)

        # Workflow & Lifecycle
        self.assertIn('From Machine Fault to Resolution', content)
        self.assertIn('Every Fault Has a Clear Lifecycle', content)
        self.assertIn('OPEN', content)
        self.assertIn('ASSIGNED', content)
        self.assertIn('ACCEPTED', content)
        self.assertIn('IN_PROGRESS', content)
        self.assertIn('RESOLVED', content)

        # Problem & Features
        self.assertIn('When a machine stops, every minute matters.', content)
        self.assertIn('Built for Factory Operations', content)

        # Dashboard CTA
        self.assertIn('/dashboard/', content)
        self.assertIn('Open Dashboard', content)

