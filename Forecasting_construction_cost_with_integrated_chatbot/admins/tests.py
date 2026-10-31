from django.test import TestCase, override_settings
from django.urls import reverse

from users.models import ConstructionRate, LabourContact, UserRegistrationModel


def make_user():
    return UserRegistrationModel.objects.create(
        name='Asha', loginid='asha', email='a@example.com', password='x',
        mobile='9876543210', locality='Area', address='Street',
    )


@override_settings(ADMIN_LOGIN='boss', ADMIN_PASSWORD='s3cret')
class AdminPanelTests(TestCase):
    def login(self):
        return self.client.post(reverse('AdminLoginCheck'), {'loginid': 'boss', 'password': 's3cret'})

    def test_login(self):
        wrong = self.client.post(reverse('AdminLoginCheck'), {'loginid': 'boss', 'password': 'no'}, follow=True)
        self.assertContains(wrong, 'check your login details')
        self.assertRedirects(self.login(), reverse('AdminHome'))

    def test_every_page_requires_admin(self):
        user = make_user()
        for name in ('AdminHome', 'RegisterUsersView', 'manage_rates', 'manage_labour'):
            self.assertRedirects(self.client.get(reverse(name)), reverse('AdminLoginCheck'))
        self.assertRedirects(self.client.post(reverse('delete_users', args=[user.id])), reverse('AdminLoginCheck'))
        self.assertTrue(UserRegistrationModel.objects.filter(id=user.id).exists())

    def test_pages_render(self):
        self.login()
        for name in ('AdminHome', 'RegisterUsersView', 'manage_rates', 'manage_labour'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_user_actions_need_post(self):
        self.login()
        user = make_user()
        self.assertEqual(self.client.get(reverse('delete_users', args=[user.id])).status_code, 405)
        self.client.post(reverse('activate_users', args=[user.id]))
        user.refresh_from_db()
        self.assertEqual(user.status, 'active')
        self.client.post(reverse('deactivate_users', args=[user.id]))
        user.refresh_from_db()
        self.assertEqual(user.status, 'deactivated')
        self.client.post(reverse('delete_users', args=[user.id]))
        self.assertFalse(UserRegistrationModel.objects.exists())

    def rate_form(self, **changes):
        data = {f'rate_{r.id}': str(r.rate) for r in ConstructionRate.objects.all()}
        data.update(changes)
        return data

    def test_rates_edit_and_validation(self):
        self.login()
        rate = ConstructionRate.objects.first()
        self.client.post(reverse('manage_rates'), self.rate_form(**{f'rate_{rate.id}': '12345.50'}))
        rate.refresh_from_db()
        self.assertEqual(float(rate.rate), 12345.50)
        response = self.client.post(reverse('manage_rates'), self.rate_form(**{f'rate_{rate.id}': '-1'}), follow=True)
        self.assertContains(response, 'Nothing was saved')
        rate.refresh_from_db()
        self.assertEqual(float(rate.rate), 12345.50)

    def test_labour_add_and_actions(self):
        self.login()
        self.client.post(reverse('manage_labour'), {
            'name': 'Ravi', 'trade': 'mason', 'phone': '9876543210', 'city': 'Pune',
            'experience_years': 2, 'consent': 'on',
        })
        worker = LabourContact.objects.get()
        self.assertEqual(worker.status, 'approved')
        pending = LabourContact.objects.create(name='New', trade='mason', phone='9876543211', city='Pune', latitude=1, longitude=1)
        self.assertEqual(self.client.get(reverse('manage_labour')).context['page'][0], pending)
        pending.delete()
        self.client.post(reverse('labour_action', args=[worker.id, 'unavailable']))
        worker.refresh_from_db()
        self.assertFalse(worker.is_available)
        LabourContact.objects.update(status='pending')
        self.client.post(reverse('labour_action', args=[worker.id, 'approve']))
        worker.refresh_from_db()
        self.assertEqual(worker.status, 'approved')
        self.client.post(reverse('labour_action', args=[worker.id, 'delete']))
        self.assertFalse(LabourContact.objects.exists())
