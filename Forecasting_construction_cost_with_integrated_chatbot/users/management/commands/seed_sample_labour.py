from django.core.management.base import BaseCommand

from users.labour import KNOWN_PLACES
from users.models import LabourContact

CITIES = ['Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Hyderabad', 'Pune', 'Kochi',
          'Shimla', 'Manali', 'Nainital', 'Darjeeling', 'Ooty', 'Munnar']
WAGES = {'mason': 900, 'carpenter': 950, 'electrician': 1000, 'plumber': 950, 'painter': 800,
         'bar_bender': 850, 'welder': 1000, 'tiler': 900, 'helper': 600, 'contractor': 2000}


class Command(BaseCommand):
    help = 'Add placeholder labour listings for demos, or remove them with --clear.'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Delete all sample listings')

    def handle(self, *args, **options):
        deleted, _ = LabourContact.objects.filter(is_sample=True).delete()
        if options['clear']:
            self.stdout.write(f'Removed {deleted} sample listings.')
            return

        # Indian mobile numbers are normally issued from 6-9, so the 50000 prefix avoids
        # real subscribers, and example.com is a reserved domain.
        records = []
        for city_index, city in enumerate(CITIES):
            lat, lng = KNOWN_PLACES[city.lower()]
            for trade_index, (trade, label) in enumerate(LabourContact.TRADE_CHOICES):
                number = city_index * 100 + trade_index
                records.append(LabourContact(
                    name=f'Sample {label} ({city})',
                    trade=trade,
                    phone=f'50000{number:05d}',
                    email=f'sample{number}@example.com',
                    city=city,
                    locality=f'Sample Area {trade_index % 4 + 1}',
                    latitude=lat + (trade_index - 5) * 0.012,
                    longitude=lng + (trade_index % 3 - 1) * 0.015,
                    daily_wage=WAGES[trade] + city_index * 10,
                    experience_years=2 + (number % 14),
                    is_available=trade_index % 5 != 4,
                    status=LabourContact.APPROVED,
                    is_sample=True,
                ))
        LabourContact.objects.bulk_create(records)
        self.stdout.write(f'Added {len(records)} sample listings.')
