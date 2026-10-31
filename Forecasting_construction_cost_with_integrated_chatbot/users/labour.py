"""Locating places and finding nearby workers."""
import logging
import math
import time

import requests
from django.core.cache import cache

from .models import LabourContact

logger = logging.getLogger(__name__)

USER_AGENT = 'ConstructionCostEstimator/1.0 (student project)'
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
OVERPASS_URL = 'https://overpass-api.de/api/interpreter'
OSM_MAX_RADIUS_KM = 50
OSM_ATTEMPTS = 2
OSM_RETRY_SECONDS = 2

KNOWN_PLACES = {
    'mumbai': (19.0760, 72.8777), 'delhi': (28.6139, 77.2090), 'new delhi': (28.6139, 77.2090),
    'bangalore': (12.9716, 77.5946), 'bengaluru': (12.9716, 77.5946), 'chennai': (13.0827, 80.2707),
    'hyderabad': (17.3850, 78.4867), 'pune': (18.5204, 73.8567), 'kolkata': (22.5726, 88.3639),
    'ahmedabad': (23.0225, 72.5714), 'jaipur': (26.9124, 75.7873), 'lucknow': (26.8467, 80.9462),
    'kochi': (9.9312, 76.2673), 'visakhapatnam': (17.6868, 83.2185), 'vijayawada': (16.5062, 80.6480),
    'warangal': (17.9689, 79.5941), 'guwahati': (26.1445, 91.7362), 'srinagar': (34.0837, 74.7973),
    'shimla': (31.1048, 77.1734), 'manali': (32.2432, 77.1892), 'nainital': (29.3803, 79.4636),
    'dehradun': (30.3165, 78.0322), 'mussoorie': (30.4598, 78.0644), 'darjeeling': (27.0410, 88.2663),
    'ooty': (11.4102, 76.6950), 'kodaikanal': (10.2381, 77.4892), 'munnar': (10.0889, 77.0595),
    'gangtok': (27.3389, 88.6065),
}

# OpenStreetMap tags for each trade: (tag, allowed values)
OSM_TAGS = {
    'mason': [('craft', 'stonemason|builder')],
    'carpenter': [('craft', 'carpenter')],
    'electrician': [('craft', 'electrician')],
    'plumber': [('craft', 'plumber')],
    'painter': [('craft', 'painter')],
    'bar_bender': [('craft', 'metal_construction')],
    'welder': [('craft', 'metal_construction|welder')],
    'tiler': [('craft', 'tiler')],
    'helper': [('craft', 'builder')],
    'contractor': [('craft', 'builder'), ('office', 'construction_company')],
}
OSM_ALL = [
    ('craft', 'stonemason|builder|carpenter|electrician|plumber|painter|metal_construction|welder|tiler'),
    ('office', 'construction_company'),
]


def distance_km(lat1, lng1, lat2, lng2):
    """Great-circle distance using the haversine formula."""
    lat1, lng1, lat2, lng2 = map(math.radians, (lat1, lng1, lat2, lng2))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def resolve_location(text):
    """Turn a place name into (lat, lng), or None if it cannot be found."""
    place = ' '.join(text.lower().split())
    if not place:
        return None
    if place in KNOWN_PLACES:
        return KNOWN_PLACES[place]
    # "Locality, City": fall back to the city if the locality cannot be looked up
    parts = [part.strip() for part in place.split(',')]
    fallback = next((KNOWN_PLACES[part] for part in parts if part in KNOWN_PLACES), None)

    cache_key = 'geocode:' + place.replace(' ', '_')[:200]
    cached = cache.get(cache_key)
    if cached:
        return cached
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={'q': place, 'format': 'jsonv2', 'limit': 1, 'countrycodes': 'in'},
            headers={'User-Agent': USER_AGENT},
            timeout=6,
        )
        response.raise_for_status()
        results = response.json()
    except (requests.RequestException, ValueError) as error:
        logger.warning('Geocoding failed for %r: %s', place, error)
        return fallback
    if not results:
        return fallback
    coords = (float(results[0]['lat']), float(results[0]['lon']))
    cache.set(cache_key, coords, 60 * 60 * 24)
    return coords


def search_labour(lat, lng, trade='', radius_km=50, available_only=False):
    """Approved directory entries within the radius, nearest first."""
    queryset = LabourContact.objects.filter(status=LabourContact.APPROVED)
    if trade:
        queryset = queryset.filter(trade=trade)
    if available_only:
        queryset = queryset.filter(is_available=True)
    results = []
    for worker in queryset:
        worker.distance = distance_km(lat, lng, worker.latitude, worker.longitude)
        if worker.distance <= radius_km:
            results.append(worker)
    return sorted(results, key=lambda w: w.distance)


def nearest_labour(lat, lng, trade='', available_only=False, limit=3):
    """The closest entries at any distance, for when nothing is in range."""
    return search_labour(lat, lng, trade, radius_km=math.inf, available_only=available_only)[:limit]


def search_openstreetmap(lat, lng, trade='', radius_km=50):
    """Businesses mapped on OpenStreetMap near a point that publish contact details.

    Raises requests.RequestException if the public API is unavailable.
    """
    metres = int(min(radius_km, OSM_MAX_RADIUS_KM) * 1000)
    selectors = ''.join(
        f'nwr["{tag}"~"^({values})$"](around:{metres},{lat},{lng});'
        for tag, values in OSM_TAGS.get(trade, OSM_ALL)
    )
    cache_key = f'osm:{round(lat, 3)}:{round(lng, 3)}:{trade}:{metres}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    query = f'[out:json][timeout:20];({selectors});out center tags 200;'
    for attempt in range(OSM_ATTEMPTS):
        try:
            response = requests.post(OVERPASS_URL, data={'data': query}, headers={'User-Agent': USER_AGENT}, timeout=25)
            response.raise_for_status()
            elements = response.json().get('elements', [])
            break
        except (requests.RequestException, ValueError) as error:
            logger.warning('OpenStreetMap search failed (attempt %s): %s', attempt + 1, error)
            if attempt == OSM_ATTEMPTS - 1:
                raise requests.RequestException(str(error)) from error
            time.sleep(OSM_RETRY_SECONDS)

    places = []
    for element in elements:
        tags = element.get('tags', {})
        phone = tags.get('phone') or tags.get('contact:phone') or tags.get('contact:mobile') or tags.get('mobile')
        email = tags.get('email') or tags.get('contact:email')
        place_lat = element.get('lat', element.get('center', {}).get('lat'))
        place_lng = element.get('lon', element.get('center', {}).get('lon'))
        if not (phone or email) or place_lat is None or place_lng is None:
            continue
        address = ', '.join(filter(None, (tags.get('addr:street'), tags.get('addr:suburb'), tags.get('addr:city'))))
        places.append({
            'name': tags.get('name', 'Unnamed business'),
            'category': (tags.get('craft') or tags.get('office') or '').replace('_', ' ').title(),
            'phone': phone or '',
            'email': email or '',
            'website': tags.get('website') or tags.get('contact:website') or '',
            'address': address,
            'distance_km': round(distance_km(lat, lng, place_lat, place_lng), 1),
        })
    places.sort(key=lambda p: p['distance_km'])
    cache.set(cache_key, places, 60 * 60)
    return places
