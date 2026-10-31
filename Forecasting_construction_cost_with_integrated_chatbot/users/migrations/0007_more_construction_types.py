from django.db import migrations

# Indicative multipliers on the general building rate, editable from the admin panel.
# These are planning assumptions rather than published figures.
NEW_TYPES = [
    # slug, name, base type, keywords, multiplier, display order
    ('apartment', 'Apartment', 'Residential', 'apartment,apartments,flats', 1.10, 1),
    ('house', 'Independent House / Villa', 'Residential', 'house,houses,home,villa,villas,bungalow', 1.05, 2),
    ('office', 'Office Building', 'Commercial', 'office,offices', 1.10, 4),
    ('mall', 'Shopping Mall', 'Commercial', 'mall,malls,shopping,shop,shops', 1.25, 5),
    ('hotel', 'Hotel', 'Commercial', 'hotel,hotels,resort,resorts', 1.35, 6),
    ('hospital', 'Hospital', 'Commercial', 'hospital,hospitals,clinic', 1.60, 7),
    ('school', 'School / College', 'Commercial', 'school,schools,college,colleges', 0.95, 8),
    ('factory', 'Factory / Warehouse', 'Commercial', 'factory,factories,warehouse,warehouses,industrial', 0.80, 9),
]
EXISTING_ORDER = {'residential': 0, 'commercial': 3, 'bridge': 10, 'road': 11, 'tunnel': 12, 'retaining-wall': 13}


def add_types(apps, schema_editor):
    Type = apps.get_model('users', 'ConstructionType')
    Rate = apps.get_model('users', 'ConstructionRate')
    for slug, order in EXISTING_ORDER.items():
        Type.objects.filter(slug=slug).update(display_order=order)
    Type.objects.filter(slug='residential').update(ml_building_type='Residential', keywords='residential')
    Type.objects.filter(slug='commercial').update(ml_building_type='Commercial', keywords='commercial')

    for slug, name, base, keywords, multiplier, order in NEW_TYPES:
        construction_type = Type.objects.create(
            slug=slug, name=name, unit='sq.ft', keywords=keywords, material_pct=76, labour_pct=24,
            ml_building_type=base, display_order=order,
        )
        for base_rate in Rate.objects.filter(construction_type__slug=base.lower()):
            Rate.objects.create(
                construction_type=construction_type, site=base_rate.site,
                rate=round(float(base_rate.rate) * multiplier, -1),
            )


def remove_types(apps, schema_editor):
    apps.get_model('users', 'ConstructionType').objects.filter(slug__in=[t[0] for t in NEW_TYPES]).delete()


class Migration(migrations.Migration):
    dependencies = [('users', '0006_constructiontype_ml_building_type')]
    operations = [migrations.RunPython(add_types, remove_types)]
