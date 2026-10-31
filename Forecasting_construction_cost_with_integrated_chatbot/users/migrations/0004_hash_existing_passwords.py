from django.contrib.auth.hashers import identify_hasher, make_password
from django.db import migrations


def hash_passwords(apps, schema_editor):
    User = apps.get_model('users', 'UserRegistrationModel')
    for user in User.objects.all():
        try:
            identify_hasher(user.password)
        except ValueError:
            user.password = make_password(user.password)
            user.save(update_fields=['password'])


class Migration(migrations.Migration):
    dependencies = [('users', '0003_rates_labour_and_unique_accounts')]
    operations = [migrations.RunPython(hash_passwords, migrations.RunPython.noop)]
