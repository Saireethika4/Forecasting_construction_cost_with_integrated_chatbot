"""Rate-based estimates for each construction type and site."""
from .models import ConstructionRate, ConstructionType, SiteRegion

# Cost relative to Medium, from the per-sq.ft averages in the dataset
QUALITY_FACTORS = {'Low': 0.83, 'Medium': 1.0, 'High': 1.24}
BASE_SITE = 'plain'


def rate_matrix():
    """Rows of (construction type, rates in site order) plus the site list."""
    sites = list(SiteRegion.objects.all())
    lookup = {(r.construction_type_id, r.site_id): r for r in ConstructionRate.objects.all()}
    rows = [
        {'type': t, 'cells': [lookup.get((t.id, s.id)) for s in sites]}
        for t in ConstructionType.objects.all()
    ]
    return sites, rows


def estimate(construction_type, site, quantity, quality='Medium'):
    """Return the cost breakdown, or None if no rate is set for this combination."""
    rate = ConstructionRate.objects.filter(construction_type=construction_type, site=site).first()
    if rate is None:
        return None
    unit_rate = float(rate.rate) * QUALITY_FACTORS[quality]
    total = unit_rate * quantity
    return {
        'unit_rate': unit_rate,
        'total': total,
        'material': total * construction_type.material_pct / 100,
        'labour': total * construction_type.labour_pct / 100,
        'other': total * construction_type.other_pct / 100,
    }


def compare_sites(construction_type, quantity, quality='Medium'):
    """The same project priced on every site, cheapest first."""
    factor = QUALITY_FACTORS[quality]
    rows = [
        {'site': r.site, 'total': float(r.rate) * factor * quantity}
        for r in construction_type.rates.select_related('site')
    ]
    return sorted(rows, key=lambda row: row['total'])


def building_multiplier(construction_type, site):
    """Cost of this building on this site compared with the ML model's base type on plain ground."""
    base = ConstructionRate.objects.filter(
        construction_type__slug=construction_type.ml_building_type.lower(), site__slug=BASE_SITE,
    ).first()
    rate_filter = {'site': site} if site else {'site__slug': BASE_SITE}
    rate = construction_type.rates.filter(**rate_filter).first()
    if base is None or rate is None:
        return 1.0
    return float(rate.rate) / float(base.rate)
