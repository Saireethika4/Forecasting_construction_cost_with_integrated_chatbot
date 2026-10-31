import unittest.mock
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import requests
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from . import labour, ml, rates
from .models import ConstructionRate, ConstructionType, LabourContact, SiteRegion, UserRegistrationModel


def make_user(status='active', email='asha@example.com', password='Passw0rdX'):
    return UserRegistrationModel.objects.create(
        name='Asha', loginid='asha', email=email, password=make_password(password),
        mobile='9876543210', locality='Area', address='Street', status=status,
    )


class LoggedInTestCase(TestCase):
    def setUp(self):
        self.user = make_user()
        session = self.client.session
        session['id'] = self.user.id
        session.save()


class RegistrationAndLoginTests(TestCase):
    valid = {'name': 'Sai Reethika', 'loginid': 'sai1', 'email': 'Sai@Example.com', 'password': 'Passw0rdX',
             'mobile': '9876543210', 'locality': 'Area', 'address': 'Street'}

    def test_registration_hashes_password_and_waits_for_approval(self):
        response = self.client.post(reverse('UserRegisterForm'), self.valid)
        self.assertRedirects(response, reverse('UserLogin'))
        user = UserRegistrationModel.objects.get()
        self.assertEqual(user.status, 'waiting')
        self.assertEqual(user.email, 'sai@example.com')
        self.assertNotEqual(user.password, 'Passw0rdX')
        self.assertTrue(check_password('Passw0rdX', user.password))

    def test_invalid_registration_shows_errors_and_keeps_input(self):
        response = self.client.post(reverse('UserRegisterForm'), {**self.valid, 'password': 'weak', 'mobile': '123'})
        self.assertContains(response, 'at least 8 characters')
        self.assertContains(response, 'Mobile must start')
        self.assertContains(response, 'Sai Reethika')
        self.assertFalse(UserRegistrationModel.objects.exists())

    def test_duplicate_email_rejected_regardless_of_case(self):
        make_user(email='sai@example.com')
        response = self.client.post(reverse('UserRegisterForm'), self.valid)
        self.assertContains(response, 'already exists')

    def test_non_image_upload_rejected(self):
        fake = SimpleUploadedFile('photo.jpg', b'not an image', content_type='image/jpeg')
        response = self.client.post(reverse('UserRegisterForm'), {**self.valid, 'image': fake})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(UserRegistrationModel.objects.exists())

    def test_login_states(self):
        make_user(status='waiting')
        response = self.client.post(reverse('UserLoginCheck'), {'email': 'asha@example.com', 'password': 'Passw0rdX'}, follow=True)
        self.assertContains(response, 'pending admin approval')
        UserRegistrationModel.objects.update(status='active')
        response = self.client.post(reverse('UserLoginCheck'), {'email': 'ASHA@example.com', 'password': 'wrong'}, follow=True)
        self.assertContains(response, 'Invalid email or password')
        response = self.client.post(reverse('UserLoginCheck'), {'email': 'ASHA@example.com', 'password': 'Passw0rdX'})
        self.assertRedirects(response, reverse('UserHome'))

    def test_pages_require_login(self):
        for name in ('UserHome', 'train', 'predict', 'dataset', 'rates', 'labour_search', 'chat'):
            self.assertRedirects(self.client.get(reverse(name)), reverse('UserLogin'), msg_prefix=name)
        self.assertEqual(self.client.get(reverse('chatbot'), {'message': 'hi'}).status_code, 401)
        self.assertEqual(self.client.get(reverse('labour_osm'), {'lat': 1, 'lng': 1}).status_code, 401)

    def test_deactivated_user_loses_access_mid_session(self):
        user = make_user()
        session = self.client.session
        session['id'] = user.id
        session.save()
        self.assertEqual(self.client.get(reverse('UserHome')).status_code, 200)
        UserRegistrationModel.objects.update(status='deactivated')
        self.assertRedirects(self.client.get(reverse('UserHome')), reverse('UserLogin'))

    def test_public_pages_render(self):
        for name in ('index', 'UserLogin', 'UserRegister', 'AdminLogin', 'labour_register'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)


class ModelTests(LoggedInTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = TemporaryDirectory()
        cls.patches = [
            patch.object(ml, 'ARTIFACT_PATH', Path(cls.tmp.name) / 'model.joblib'),
            patch.object(ml, 'PLOTS_DIR', Path(cls.tmp.name) / 'plots'),
        ]
        for p in cls.patches:
            p.start()
        ml._cached.update(mtime=None, bundle=None)
        cls.bundle = ml.train_models()

    @classmethod
    def tearDownClass(cls):
        for p in cls.patches:
            p.stop()
        ml._cached.update(mtime=None, bundle=None)
        cls.tmp.cleanup()
        super().tearDownClass()

    def post_prediction(self, **overrides):
        data = {'area': 2000, 'floors': 2, 'city': 'Mumbai', 'site': 'plain', 'quality': 'Medium', 'btype': 'Residential', **overrides}
        return self.client.post(reverse('predict'), data)

    def test_training_produces_accurate_models_and_plots(self):
        self.assertGreater(self.bundle['metrics']['xgb']['test_r2'], 0.99)
        self.assertLess(self.bundle['metrics'][('xgb')]['mape'], 2)
        for name in ('actual_vs_pred', 'error', 'feature'):
            self.assertTrue((ml.PLOTS_DIR / f'{name}.png').exists())

    def test_training_page_posts_and_shows_results(self):
        response = self.client.post(reverse('train'), follow=True)
        self.assertContains(response, 'Training complete')
        self.assertContains(response, 'Testing Score')

    def test_prediction_is_close_to_dataset_without_cost_inputs(self):
        df = ml.load_dataset()
        row = df.iloc[0]
        result = ml.predict_cost(int(row.Area_sqft), int(row.Floors), row.City, row.Material_Quality, row.Building_Type)
        self.assertAlmostEqual(result['total'] / row.Total_Cost, 1, delta=0.05)

    def test_prediction_scales_beyond_training_range_and_warns(self):
        small = ml.predict_cost(4000, 2, 'Mumbai', 'Medium', 'Residential')
        large = ml.predict_cost(40000, 2, 'Mumbai', 'Medium', 'Residential')
        self.assertAlmostEqual(large['total'] / small['total'], 10, delta=0.01)
        self.assertIsNone(small['warning'])
        self.assertIn('extrapolation', large['warning'])

    def test_quality_and_city_ordering(self):
        cost = lambda city, quality: ml.predict_cost(2000, 2, city, quality, 'Residential')['total']
        self.assertLess(cost('Mumbai', 'Low'), cost('Mumbai', 'High'))
        self.assertLess(cost('Hyderabad', 'Medium'), cost('Mumbai', 'Medium'))

    def test_predict_page_applies_site_factor(self):
        plain = self.post_prediction().context['result']['total']
        hill = self.post_prediction(site='hill').context['result']
        self.assertAlmostEqual(hill['total'] / plain, 4370 / 3360, places=3)
        self.assertContains(self.post_prediction(site='hill'), 'Hill Station')

    def test_predict_page_uses_known_quotes(self):
        result = self.post_prediction(material_cost='1000000', labor_cost='500000').context['result']
        self.assertEqual(result['total'], 1500000)

    def test_predict_page_handles_bad_input(self):
        for bad in ({'area': 'abc'}, {'area': '-5'}, {'city': 'Atlantis'}, {'site': 'moon'}, {'material_cost': 'nan'}):
            response = self.post_prediction(**bad)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['errors'], bad)

    def chat(self, message):
        return self.client.get(reverse('chatbot'), {'message': message}).json()['response']

    def test_chat_prediction_and_prompts_for_city(self):
        self.assertIn('Estimated total', self.chat('Predict cost for 2000 sqft in Mumbai'))
        self.assertIn('Hill Station', self.chat('Estimate 2,000 sq ft in Delhi on a hill station'))
        self.assertIn('Which city', self.chat('Estimate cost for 3000 sqft'))

    def test_chat_guided_flow(self):
        self.assertIn('area', self.chat('start prediction'))
        self.assertIn('whole number', self.chat('lots'))
        self.assertIn('floors', self.chat('2000'))
        self.assertIn('city', self.chat('2'))
        self.assertIn("didn't recognise", self.chat('Atlantis'))
        self.assertIn('quality', self.chat('Mumbai'))
        self.assertIn('building type', self.chat('high'))
        self.assertIn('site', self.chat('Commercial'))
        self.assertIn('Estimated total', self.chat('river'))
        self.assertNotIn('chat_flow', self.client.session)

    def test_chat_flow_can_be_cancelled(self):
        self.chat('start prediction')
        self.assertIn('cancelled', self.chat('cancel'))


class ChatbotTests(LoggedInTestCase):
    def chat(self, message):
        return self.client.get(reverse('chatbot'), {'message': message}).json()['response']

    def test_words_containing_hi_are_not_greetings(self):
        reply = self.chat('Which cities are available?')
        self.assertIn('Hyderabad', reply)
        self.assertNotIn('Hello', reply)
        self.assertIn('Hello', self.chat('Hi!'))

    def test_facts_and_statistics(self):
        self.assertIn('Commercial', self.chat('what building types are there'))
        self.assertIn('cost factors', self.chat('What factors affect cost?'))
        self.assertIn('Delhi statistics', self.chat('Average cost in Delhi'))
        self.assertIn('Residential statistics', self.chat('Residential building statistics'))
        self.assertIn('Overall statistics', self.chat('average cost'))
        self.assertNotIn('Low', self.chat('show statistics below ground').split('\n')[0])

    def test_rates(self):
        reply = self.chat('Bridge rate on a hill station')
        self.assertIn('₹130,000', reply)
        self.assertIn('Bridge rates per', self.chat('how much does a bridge cost'))
        self.assertIn('₹65,000,000', self.chat('cost of a 500 sqm bridge on a hill station'))
        self.assertIn('Rates on Water Body', self.chat('rates on a water body'))

    def test_labour(self):
        call_command('seed_sample_labour', verbosity=0, stdout=open('/dev/null', 'w'))
        reply = self.chat('Masons near Hyderabad')
        self.assertIn('Sample Mason (Hyderabad)', reply)
        self.assertIn('not a real contact', reply)
        self.assertIn('Which city', self.chat('I need a plumber'))
        self.assertIn('statistics', self.chat('average labour cost in Mumbai'))

    @override_settings(GEMINI_API_KEY='')
    def test_unknown_question_without_ai_still_helps(self):
        self.assertIn('I can help with', self.chat('tell me a joke'))

    @override_settings(GEMINI_API_KEY='x')
    def test_ai_failure_still_helps(self):
        with patch('google.genai.Client', side_effect=RuntimeError('down')):
            self.assertIn('I can help with', self.chat('tell me a joke'))

    def test_empty_message(self):
        self.assertIn('type a question', self.chat('   '))


class RatesTests(LoggedInTestCase):
    def test_every_type_has_a_rate_for_every_site(self):
        self.assertEqual(ConstructionRate.objects.count(), ConstructionType.objects.count() * SiteRegion.objects.count())

    def test_estimate_breakdown_adds_up(self):
        bridge = ConstructionType.objects.get(slug='bridge')
        hill = SiteRegion.objects.get(slug='hill')
        result = rates.estimate(bridge, hill, 100, 'High')
        self.assertAlmostEqual(result['total'], 130000 * 1.24 * 100)
        self.assertAlmostEqual(result['material'] + result['labour'] + result['other'], result['total'])

    def test_bridge_costs_more_on_hill_and_water_than_plain(self):
        bridge = ConstructionType.objects.get(slug='bridge')
        rows = {r['site'].slug: r['total'] for r in rates.compare_sites(bridge, 1)}
        self.assertGreater(rows['hill'], rows['plain'])
        self.assertGreater(rows['water'], rows['plain'])

    def test_page_estimates_and_compares(self):
        response = self.client.get(reverse('rates'), {'type': 'bridge', 'site': 'water', 'quantity': '200', 'quality': 'Medium'})
        self.assertAlmostEqual(response.context['result']['total'], 153000 * 200)
        self.assertEqual(len(response.context['comparison']), SiteRegion.objects.count())
        self.assertContains(response, 'Same project on other sites')

    def test_page_rejects_bad_input(self):
        for quantity in ('0', '-1', 'abc', 'inf', 'nan'):
            response = self.client.get(reverse('rates'), {'type': 'bridge', 'site': 'water', 'quantity': quantity})
            self.assertContains(response, 'quantity above zero')
        self.assertContains(self.client.get(reverse('rates'), {'type': 'x', 'site': 'y', 'quantity': '1'}), 'Please choose')


class LabourTests(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        sleep = patch.object(labour.time, 'sleep')
        sleep.start()
        self.addCleanup(sleep.stop)

    def make(self, **kwargs):
        defaults = dict(name='Ravi', trade='mason', phone='9876543210', city='Shimla', latitude=31.1, longitude=77.17, status='approved')
        return LabourContact.objects.create(**{**defaults, **kwargs})

    def test_distance(self):
        mumbai, delhi = labour.KNOWN_PLACES['mumbai'], labour.KNOWN_PLACES['delhi']
        self.assertAlmostEqual(labour.distance_km(*mumbai, *delhi), 1150, delta=20)

    def test_search_filters_and_sorts_by_distance(self):
        far = self.make(name='Far', latitude=31.4)
        near = self.make(name='Near')
        self.make(name='Pending', status='pending')
        self.make(name='Other trade', trade='plumber')
        self.make(name='Busy', is_available=False)
        lat, lng = labour.KNOWN_PLACES['shimla']
        found = labour.search_labour(lat, lng, 'mason', 50, available_only=True)
        self.assertEqual([w.id for w in found], [near.id, far.id])

    def test_page_shows_contact_details(self):
        self.make(email='ravi@example.com')
        response = self.client.get(reverse('labour_search'), {'location': 'Shimla', 'radius': 25})
        self.assertContains(response, 'tel:+919876543210')
        self.assertContains(response, 'ravi@example.com')

    def test_browser_coordinates_are_used(self):
        self.make()
        response = self.client.get(reverse('labour_search'), {'lat': '31.1', 'lng': '77.17', 'location': ''})
        self.assertEqual(len(response.context['results']), 1)

    def test_empty_radius_suggests_nearest(self):
        self.make()
        response = self.client.get(reverse('labour_search'), {'location': 'Mumbai', 'radius': 10})
        self.assertEqual(response.context['results'], [])
        self.assertEqual(len(response.context['nearest']), 1)
        self.assertContains(response, 'closest listings')

    def test_unknown_location_explained(self):
        with patch.object(labour.requests, 'get', side_effect=requests.ConnectionError):
            response = self.client.get(reverse('labour_search'), {'location': 'Zzzzville'})
        self.assertContains(response, 'could not find')

    def test_sample_records_are_marked_and_not_dialable(self):
        call_command('seed_sample_labour', stdout=open('/dev/null', 'w'))
        response = self.client.get(reverse('labour_search'), {'location': 'Manali'})
        self.assertContains(response, 'Sample records:')
        self.assertNotContains(response, 'tel:+9150000')
        self.assertFalse(LabourContact.objects.filter(is_sample=True).exclude(phone__startswith='50000').exists())
        call_command('seed_sample_labour', clear=True, stdout=open('/dev/null', 'w'))
        self.assertFalse(LabourContact.objects.exists())

    def test_self_registration_needs_consent_and_approval(self):
        data = {'name': 'Ravi', 'trade': 'mason', 'phone': '9876543210', 'city': 'Ooty', 'experience_years': 3}
        self.assertContains(self.client.post(reverse('labour_register'), data), 'This field is required')
        self.assertFalse(LabourContact.objects.exists())
        self.client.post(reverse('labour_register'), {**data, 'consent': 'on'})
        worker = LabourContact.objects.get()
        self.assertEqual(worker.status, 'pending')
        self.assertEqual((worker.latitude, worker.longitude), labour.KNOWN_PLACES['ooty'])
        self.assertEqual(labour.search_labour(*labour.KNOWN_PLACES['ooty']), [])

    def test_openstreetmap_keeps_only_places_with_contact_details(self):
        elements = [
            {'lat': 31.1, 'lon': 77.17, 'tags': {'name': 'A Builders', 'craft': 'builder', 'phone': '+91 11111'}},
            {'center': {'lat': 31.2, 'lon': 77.17}, 'tags': {'name': 'B Co', 'office': 'construction_company', 'contact:email': 'b@example.com'}},
            {'lat': 31.1, 'lon': 77.17, 'tags': {'name': 'No contact', 'craft': 'builder'}},
        ]
        with patch.object(labour.requests, 'post') as post:
            post.return_value.json.return_value = {'elements': elements}
            response = self.client.get(reverse('labour_osm'), {'lat': 31.1, 'lng': 77.17, 'trade': 'contractor', 'radius': 500})
        data = response.json()
        self.assertEqual([p['name'] for p in data['places']], ['A Builders', 'B Co'])
        self.assertEqual(data['radius'], labour.OSM_MAX_RADIUS_KM)

    def test_openstreetmap_retries_then_caches(self):
        good = patch.object(labour.requests, 'post', side_effect=[requests.Timeout(), unittest.mock.Mock(**{'json.return_value': {'elements': []}})])
        with good as post:
            self.assertEqual(labour.search_openstreetmap(31.1, 77.17), [])
            self.assertEqual(labour.search_openstreetmap(31.1, 77.17), [])
        self.assertEqual(post.call_count, 2)

    def test_openstreetmap_outage_reported(self):
        with patch.object(labour.requests, 'post', side_effect=requests.Timeout):
            response = self.client.get(reverse('labour_osm'), {'lat': 31.1, 'lng': 77.17})
        self.assertEqual(response.status_code, 503)
        self.assertIn('busy', response.json()['error'])

    def test_openstreetmap_rejects_bad_coordinates(self):
        self.assertEqual(self.client.get(reverse('labour_osm'), {'lat': 'x', 'lng': '1'}).status_code, 400)
        self.assertEqual(self.client.get(reverse('labour_osm'), {'lat': '91', 'lng': '1'}).status_code, 400)


class DatasetTests(LoggedInTestCase):
    def test_paginates(self):
        response = self.client.get(reverse('dataset'), {'page': 2})
        self.assertContains(response, 'Page 2 of 200')
        self.assertContains(response, 'Total_Cost')
