from django.db import migrations

# Indicative planning rates in rupees per unit at Medium quality, editable from the admin panel.
# Buildings: dataset average for Medium quality. Roads: about ₹7.5 crore/km on plains and
# ₹25 crore/km in hills, from published ranges. Tunnels: about ₹366 crore/km, from MoRTH's plan
# of 74 tunnels (273 km, ₹1 trillion). Bridges, retaining walls and all other site differences
# are engineering assumptions rather than published figures.
SITES = [
    ('plain', 'Plain / Normal Ground', 'Baseline: easy access and ordinary foundations.', 'plain,plains,normal,flat'),
    ('hill', 'Hill Station', 'Steep access, slope stabilisation, material carriage and a shorter working season.', 'hill,hills,hilly,hill station,hill stations,mountain,mountains'),
    ('water', 'Water Body (River / Lake)', 'Deep foundations, cofferdams, dewatering and floating equipment.', 'water,water body,water bodies,river,rivers,lake,lakes,reservoir'),
    ('coastal', 'Coastal / Marine', 'Corrosion-resistant materials, tidal working windows and wave exposure.', 'coast,coastal,marine,sea,seaside,beach'),
    ('desert', 'Desert / Arid', 'Water carriage, heat-limited working hours and shifting sand.', 'desert,arid,sand,sandy'),
    ('forest', 'Forest / Remote', 'Long haul distances, clearances and worker camps.', 'forest,remote,jungle,rural'),
    ('urban', 'Dense Urban', 'Traffic management, night work, utility shifting and tight access.', 'urban,dense urban,city centre,congested,metro'),
]
TYPES = [
    # slug, name, unit, keywords, material %, labour %, rates by site in SITES order
    ('residential', 'Residential Building', 'sq.ft', 'residential,house,home,apartment', 76, 24,
     [3360, 4370, 5380, 4030, 3860, 4200, 3860]),
    ('commercial', 'Commercial Building', 'sq.ft', 'commercial,office,shop,mall', 76, 24,
     [3360, 4370, 5380, 4030, 3860, 4200, 3860]),
    ('bridge', 'Bridge', 'sq.m of deck', 'bridge,bridges,flyover,overpass', 55, 20,
     [90000, 130000, 153000, 171000, 99000, 121000, 135000]),
    ('road', 'Road (2-lane)', 'km', 'road,roads,highway,highways', 55, 15,
     [75000000, 250000000, 225000000, 105000000, 86000000, 120000000, 135000000]),
    ('tunnel', 'Tunnel', 'running metre', 'tunnel,tunnels', 45, 20,
     [2930000, 3660000, 8050000, 5490000, 2930000, 4030000, 5120000]),
    ('retaining-wall', 'Retaining Wall', 'running metre', 'retaining wall,retaining walls,embankment', 60, 28,
     [25000, 40000, 45000, 37500, 27500, 32500, 35000]),
]


def seed(apps, schema_editor):
    Site = apps.get_model('users', 'SiteRegion')
    Type = apps.get_model('users', 'ConstructionType')
    Rate = apps.get_model('users', 'ConstructionRate')
    sites = [
        Site.objects.create(slug=slug, name=name, description=description, keywords=keywords, display_order=order)
        for order, (slug, name, description, keywords) in enumerate(SITES)
    ]
    for order, (slug, name, unit, keywords, material, labour, rates) in enumerate(TYPES):
        construction_type = Type.objects.create(
            slug=slug, name=name, unit=unit, keywords=keywords,
            material_pct=material, labour_pct=labour, display_order=order,
        )
        for site, rate in zip(sites, rates):
            Rate.objects.create(construction_type=construction_type, site=site, rate=rate)


def unseed(apps, schema_editor):
    apps.get_model('users', 'ConstructionType').objects.all().delete()
    apps.get_model('users', 'SiteRegion').objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [('users', '0004_hash_existing_passwords')]
    operations = [migrations.RunPython(seed, unseed)]
