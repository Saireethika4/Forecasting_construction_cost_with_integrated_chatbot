"""Chatbot answers: guided prediction, rates, labour, statistics, then Gemini."""
import logging
import re

import requests
from django.conf import settings

from . import labour, ml, rates
from .models import ConstructionType, LabourContact, SiteRegion

logger = logging.getLogger(__name__)

FLOW_KEY = 'chat_flow'
TRADE_WORDS = {
    'mason': 'mason', 'carpenter': 'carpenter', 'electrician': 'electrician', 'plumber': 'plumber',
    'painter': 'painter', 'bar bender': 'bar_bender', 'welder': 'welder', 'tiler': 'tiler',
    'tile layer': 'tiler', 'helper': 'helper', 'contractor': 'contractor',
}
LABOUR_WORDS = r'labou?r(?:er)?s?|workers?|' + '|'.join(f'{word}s?' for word in TRADE_WORDS)


def has_word(message, pattern):
    return re.search(rf'\b(?:{pattern})\b', message) is not None


def money(value):
    return f'₹{value:,.0f}'


def find_keyword_match(message, objects):
    for obj in objects:
        words = [w.strip() for w in obj.keywords.split(',') if w.strip()]
        if words and has_word(message, '|'.join(map(re.escape, words))):
            return obj
    return None


def find_value(message, values):
    for value in values:
        if has_word(message, re.escape(value.lower())):
            return value
    return None


def parse_number(text):
    match = re.search(r'\d[\d,]*(?:\.\d+)?', text)
    return float(match.group().replace(',', '')) if match else None


def parse_area(message):
    match = re.search(r'(\d[\d,]*)\s*(?:sq\.?\s*ft|sqft|square\s*f(?:ee|oo)t|sft)', message)
    if match:
        return int(match.group(1).replace(',', ''))
    for number in re.findall(r'\d[\d,]*', message):
        value = int(number.replace(',', ''))
        if value >= 100:
            return value
    return None


# ---- Prediction ----

def prediction_text(area, floors, city, quality, construction_type, site=None):
    result = ml.predict_cost(area, floors, city, quality, construction_type.ml_building_type)
    multiplier = rates.building_multiplier(construction_type, site)
    total = result['total'] * multiplier
    lines = [
        '**🤖 Cost Prediction**', '',
        f'• {area:,} sq.ft, {floors} floor(s), {construction_type.name}',
        f'• {city}, {quality} quality' + (f', {site.name}' if site else ''), '',
        f'**Estimated total: {money(total)}** (±{result["error_p95"]:.1f}% model error)',
        f'• Material: {money(result["material"] * multiplier)}',
        f'• Labour: {money(result["labour"] * multiplier)}',
        f'• Per sq.ft: {money(total / area)}',
    ]
    if multiplier != 1.0:
        lines.append(f'• Includes ×{multiplier:.2f} type and site factor from the rate table (an indicative assumption)')
    if result['warning']:
        lines += ['', f'⚠️ {result["warning"]}']
    return '\n'.join(lines)


def building_types():
    return ConstructionType.objects.exclude(ml_building_type='')


def flow_steps():
    options = ml.form_options()
    return [
        ('area', 'What is the built-up **area in sq.ft**? (for example 2000)', None),
        ('floors', 'How many **floors**?', None),
        ('city', 'Which **city**? ' + ', '.join(options['city_states']), list(options['city_states'])),
        ('quality', 'Which **material quality**? ' + ', '.join(options['qualities']), options['qualities']),
        ('type', 'Which **building type**? ' + ', '.join(t.name for t in building_types()),
         [t.name for t in building_types()]),
        ('site', 'Which **site**? ' + ', '.join(s.name for s in SiteRegion.objects.all()),
         [s.name for s in SiteRegion.objects.all()]),
    ]


def start_flow(request):
    request.session[FLOW_KEY] = {}
    return "Let's estimate your project. Type **cancel** at any time.\n\n" + flow_steps()[0][1]


def continue_flow(request, message):
    if has_word(message.lower(), 'cancel|stop|quit|exit'):
        request.session.pop(FLOW_KEY, None)
        return 'Prediction cancelled. What else can I help with?'

    answers = request.session[FLOW_KEY]
    steps = flow_steps()
    key, question, choices = next(step for step in steps if step[0] not in answers)

    if choices is None:
        value = parse_number(message)
        if value is None or value < 1 or value != int(value) or (key == 'floors' and value > 100):
            return f'Please enter a whole number.\n\n{question}'
        answers[key] = int(value)
    else:
        typed = message.lower()
        match = next((c for c in choices if c.lower() == typed or has_word(typed, re.escape(c.lower()))), None)
        if match is None and key in ('site', 'type'):
            found = find_keyword_match(typed, SiteRegion.objects.all() if key == 'site' else building_types())
            match = found.name if found else None
        if match is None:
            return f"I didn't recognise that.\n\n{question}"
        answers[key] = match
    request.session[FLOW_KEY] = answers

    remaining = [step for step in steps if step[0] not in answers]
    if remaining:
        return remaining[0][1]
    request.session.pop(FLOW_KEY, None)
    site = SiteRegion.objects.filter(name=answers['site']).first()
    return prediction_text(answers['area'], answers['floors'], answers['city'], answers['quality'],
                           ConstructionType.objects.get(name=answers['type']), site)


def handle_prediction(message, df):
    if not has_word(message, r'predict|estimate|calculate|how much|cost for|price for'):
        return None
    area = parse_area(message)
    if area is None:
        return None
    city = find_value(message, df['City'].unique())
    if city is None:
        return f'Which city is the {area:,} sq.ft project in? I have data for ' + ', '.join(sorted(df['City'].unique())) + '.'
    floors_match = re.search(r'(\d+)\s*(?:-\s*)?(?:floors?|stor(?:e?y|eys|ies))', message)
    floors = int(floors_match.group(1)) if floors_match else 2
    quality = find_value(message, ['Low', 'Medium', 'High']) or 'Medium'
    named_type = find_keyword_match(message, building_types())
    construction_type = named_type or ConstructionType.objects.get(slug='residential')
    site = find_keyword_match(message, SiteRegion.objects.all())
    text = prediction_text(area, floors, city, quality, construction_type, site)
    assumed = []
    if not floors_match:
        assumed.append('2 floors')
    if not has_word(message, 'low|medium|high'):
        assumed.append('Medium quality')
    if named_type is None:
        assumed.append('Residential')
    return text + (f"\n\nAssumed: {', '.join(assumed)}." if assumed else '')


# ---- Rates ----

def handle_rates(message):
    construction_type = find_keyword_match(message, ConstructionType.objects.all())
    site = find_keyword_match(message, SiteRegion.objects.all())
    is_infrastructure = construction_type is not None and not construction_type.uses_ml
    asks_for_rate = has_word(message, r'rates?|per\s+\w+|multiplier')
    if not is_infrastructure and not (asks_for_rate and (construction_type or site)):
        return None

    if construction_type and site:
        result = rates.estimate(construction_type, site, 1)
        if result is None:
            return f'No rate is set yet for {construction_type.name} on {site.name}.'
        text = (f'**{construction_type.name} on {site.name}**\n\n'
                f'Rate: **{money(result["unit_rate"])} per {construction_type.unit}** (Medium quality)\n'
                f'{site.description}')
        quantity = parse_quantity(message)
        if quantity:
            total = result['unit_rate'] * quantity
            text += f'\n\nFor {quantity:,.0f} {construction_type.unit}: **{money(total)}**'
        return text + '\n\nThis is an indicative planning rate. See the Rates page for a full breakdown.'

    if construction_type:
        rows = construction_type.rates.select_related('site').order_by('site__display_order')
        lines = [f'• {r.site.name}: {money(float(r.rate))}' for r in rows]
        return f'**{construction_type.name} rates per {construction_type.unit}:**\n\n' + '\n'.join(lines) + \
            '\n\nTell me the site too, e.g. "' + construction_type.name.lower() + ' on a hill station".'

    rows = site.rates.select_related('construction_type').order_by('construction_type__display_order')
    lines = [f'• {r.construction_type.name}: {money(float(r.rate))} per {r.construction_type.unit}' for r in rows]
    return f'**Rates on {site.name}:**\n\n' + '\n'.join(lines)


def parse_quantity(message):
    match = re.search(r'(\d[\d,]*(?:\.\d+)?)\s*(?:sq\.?\s*m|sqm|sq\.?\s*ft|sqft|km|kilomet|m\b|met(?:er|re)|running)', message)
    return float(match.group(1).replace(',', '')) if match else None


# ---- Labour ----

def handle_labour(message):
    if not has_word(message, LABOUR_WORDS) or has_word(message, r'costs?|average|mean|statistics|percent'):
        return None
    trade = next((slug for word, slug in TRADE_WORDS.items() if has_word(message, f'{word}s?')), '')
    place = next((name for name in sorted(labour.KNOWN_PLACES, key=len, reverse=True) if has_word(message, name)), None)
    if place is None:
        return 'Which city should I search in? For example, "masons near Hyderabad". You can search any location on the Find Labour page.'
    lat, lng = labour.KNOWN_PLACES[place]
    results = labour.search_labour(lat, lng, trade, radius_km=50)[:5]
    trade_label = dict(LabourContact.TRADE_CHOICES).get(trade, 'workers')
    if not results:
        return f'I found no {trade_label} listed within 50 km of {place.title()}. The Find Labour page can also search OpenStreetMap.'
    lines = [f'**{trade_label} near {place.title()}:**', '']
    for worker in results:
        sample = ' (sample record, not a real contact)' if worker.is_sample else ''
        lines.append(f'• **{worker.name}** – {worker.get_trade_display()}, {worker.distance:.1f} km – 📞 {worker.phone}{sample}')
    return '\n'.join(lines)


# ---- Facts and statistics ----

def handle_rules(message, df):
    if has_word(message, r'which cities|available cities|supported cities|cities'):
        return f'**Cities in the dataset ({len(df):,} projects):**\n\n' + '\n'.join(f'• {c}' for c in sorted(df['City'].unique()))
    if 'building type' in message or 'types of building' in message:
        counts = df['Building_Type'].value_counts()
        return '**Building types:**\n\n' + '\n'.join(f'• **{name}**: {count:,} projects' for name, count in counts.items())
    if 'material quality' in message or 'quality level' in message:
        means = df.groupby('Material_Quality')['Total_Cost'].mean()
        return '**Material quality levels:**\n\n' + '\n'.join(f'• **{q}**: average {money(means[q])}' for q in ['Low', 'Medium', 'High'])
    if 'factor' in message and 'cost' in message:
        return ('**Main cost factors:**\n\n'
                '• **Area**: cost scales almost directly with sq.ft\n'
                '• **Material quality**: High costs about 24% more than Medium, Low about 17% less\n'
                '• **City**: Mumbai is the most expensive in this data, Hyderabad the least\n'
                '• **Site**: hills, water bodies and remote sites raise rates (see the Rates page)')
    if 'cost range' in message or 'price range' in message:
        return (f'**Cost range in the dataset:**\n\n• Minimum: {money(df["Total_Cost"].min())}\n'
                f'• Maximum: {money(df["Total_Cost"].max())}\n• Average: {money(df["Total_Cost"].mean())}')
    return None


def stats_text(title, data):
    per_sqft = (data['Total_Cost'] / data['Area_sqft']).mean()
    return (f'**{title}**\n\n• Projects: {len(data):,}\n• Average cost: {money(data["Total_Cost"].mean())}\n'
            f'• Average area: {data["Area_sqft"].mean():,.0f} sq.ft\n• Average cost per sq.ft: {money(per_sqft)}\n'
            f'• Average material cost: {money(data["Material_Cost"].mean())}\n'
            f'• Average labour cost: {money(data["Labor_Cost"].mean())}\n'
            f'• Range: {money(data["Total_Cost"].min())} – {money(data["Total_Cost"].max())}')


def handle_statistics(message, df):
    city = find_value(message, df['City'].unique())
    building_type = find_value(message, df['Building_Type'].unique())
    quality = find_value(message, ['Low', 'Medium', 'High'])
    asks = has_word(message, r'average|mean|statistics|stats|data|info|info about|cost in|costs? of')
    if city or building_type or quality:
        if not asks and not has_word(message, r'costs?|price'):
            return None
    elif not asks:
        return None
    data = df
    title = []
    if city:
        data, title = data[data['City'] == city], title + [city]
    if building_type:
        data, title = data[data['Building_Type'] == building_type], title + [building_type]
    if quality:
        data, title = data[data['Material_Quality'] == quality], title + [f'{quality} quality']
    return stats_text(' – '.join(title) + ' statistics' if title else 'Overall statistics', data)


HELP_TEXT = """**I can help with:**

• **Guided prediction**: say "start prediction"
• **Quick estimates**: "Predict cost for 2000 sqft in Mumbai on a hill station"
• **Site rates**: "Bridge rate on a water body" or "cost of a 500 sqm bridge on a hill station"
• **Nearby labour**: "Masons near Hyderabad"
• **Statistics**: "Average cost in Delhi"
• **Facts**: "Which cities are available?", "What factors affect cost?\""""


def ask_gemini(message, df):
    """Answer with Gemini, or None if it is not configured or unavailable."""
    if not settings.GEMINI_API_KEY:
        return None
    prompt = (
        'You are a construction cost assistant for India. Answer concisely and practically, and say that '
        'cost figures are estimates. Reference data: '
        f'{len(df)} building projects in {", ".join(sorted(df["City"].unique()))}; '
        f'average cost {money(df["Total_Cost"].mean())}.\n\nQuestion: {message}'
    )
    try:
        response = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent',
            headers={'x-goog-api-key': settings.GEMINI_API_KEY},
            json={'contents': [{'parts': [{'text': prompt}]}]},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except (requests.RequestException, ValueError, KeyError, IndexError) as error:
        # The exception text can contain the request details, so log only its type and status
        status = getattr(getattr(error, 'response', None), 'status_code', '')
        logger.warning('Gemini request failed: %s %s', type(error).__name__, status)
        return None


def respond(request, raw_message):
    message = ' '.join(raw_message.lower().split())
    df = ml.load_dataset()

    if FLOW_KEY in request.session:
        return continue_flow(request, raw_message.strip())
    if re.search(r'\bstart\b.*\bpredict|^predict(ion)?( cost)?$|^estimate( cost)?$', message):
        return start_flow(request)

    if re.fullmatch(r'(hello|hi+|hey|greetings|namaste|good (morning|afternoon|evening))[ !.]*', message):
        return "Hello! 👋 I'm your Construction Cost Assistant.\n\n" + HELP_TEXT
    if has_word(message, r'help|what can you do|capabilities|features'):
        return HELP_TEXT

    for handler in (
        lambda: handle_labour(message),
        lambda: handle_rates(message),
        lambda: handle_prediction(message, df),
        lambda: handle_rules(message, df),
        lambda: handle_statistics(message, df),
        lambda: ask_gemini(raw_message, df),
    ):
        reply = handler()
        if reply:
            return reply
    return "I don't have an answer for that yet.\n\n" + HELP_TEXT
