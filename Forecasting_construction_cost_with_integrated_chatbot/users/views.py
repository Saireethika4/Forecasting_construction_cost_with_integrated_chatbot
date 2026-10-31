import requests
from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from . import chatbot, labour, ml, rates
from .decorators import user_required, user_required_json
from .forms import LabourForm, UserRegistrationForm
from .models import ConstructionType, LabourContact, SiteRegion, UserRegistrationModel

RADIUS_CHOICES = [10, 25, 50, 100, 250, 500]
MAX_CHAT_MESSAGE = 500


def UserRegisterActions(request):
    if request.method != 'POST':
        return redirect('UserRegister')

    form = UserRegistrationForm(request.POST, request.FILES)
    if form.is_valid():
        form.save()
        messages.success(request, 'Registration successful! Please wait for admin approval.')
        return redirect('UserLogin')
    return render(request, 'userRegistration.html', {'form': form})


def UserLoginCheck(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        user = UserRegistrationModel.objects.filter(email__iexact=email).first()
        if user is None or not check_password(password, user.password):
            messages.error(request, 'Invalid email or password.')
        elif user.status == 'active':
            request.session.cycle_key()
            request.session['id'] = user.id
            request.session['name'] = user.name
            return redirect('UserHome')
        elif user.status == 'waiting':
            messages.warning(request, 'Your account is pending admin approval.')
        else:
            messages.error(request, 'Your account has been deactivated.')
        return redirect('UserLogin')

    return render(request, 'login.html')


@user_required
def UserHome(request):
    return render(request, 'users/userHome.html', {'user': request.app_user})


def base(request):
    return render(request, 'base.html')


def logout_view(request):
    request.session.flush()
    return redirect('index')


@user_required
def train_model_view(request):
    if request.method == 'POST':
        bundle = ml.train_models()
        messages.success(request, f'Training complete. {bundle["model_label"]} is now used for predictions.')
        return redirect('train')

    bundle = ml.trained_bundle()
    context = {}
    if bundle:
        context = {'bundle': bundle, 'metrics': bundle['metrics'], 'plot_version': ml.ARTIFACT_PATH.stat().st_mtime_ns}
    return render(request, 'users/training.html', context)


def _parse_prediction_form(post, options, construction_type):
    """Return (cleaned values, list of errors) for the prediction form."""
    errors = []
    cleaned = {}
    try:
        cleaned['area'] = float(post.get('area', ''))
        if not 0 < cleaned['area'] < float('inf'):
            raise ValueError
    except ValueError:
        errors.append('Size must be a number above zero.')
    cleaned['quality'] = post.get('quality', '')
    if cleaned['quality'] not in options['qualities']:
        errors.append('Please choose a valid material quality.')
    if construction_type and construction_type.uses_ml:
        try:
            cleaned['floors'] = int(post.get('floors', ''))
            if cleaned['floors'] < 1:
                raise ValueError
        except ValueError:
            errors.append('Floors must be a whole number of at least 1.')
        cleaned['city'] = post.get('city', '')
        if cleaned['city'] not in options['city_states']:
            errors.append('Please choose a valid city.')
    for field, label in (('material_cost', 'Material cost'), ('labor_cost', 'Labour cost')):
        raw = post.get(field, '').strip()
        cleaned[field] = None
        if raw:
            try:
                cleaned[field] = float(raw)
                if not 0 <= cleaned[field] < float('inf'):
                    raise ValueError
            except ValueError:
                errors.append(f'{label} must be a positive number or left blank.')
    return cleaned, errors


def _building_estimate(cleaned, construction_type, site, city_states):
    """ML estimate for the base building type, scaled by the rate table."""
    result = ml.predict_cost(cleaned['area'], cleaned['floors'], cleaned['city'], cleaned['quality'], construction_type.ml_building_type)
    multiplier = rates.building_multiplier(construction_type, site)
    return {
        'material': result['material'] * multiplier,
        'labour': result['labour'] * multiplier,
        'other': 0,
        'error_p95': result['error_p95'],
        'model_label': result['model_label'],
        'warning': result['warning'],
        'multiplier': multiplier,
        'place': f"{cleaned['city']}, {city_states[cleaned['city']]}",
    }


def _infrastructure_estimate(cleaned, construction_type, site):
    """Infrastructure is outside the training data, so it is priced from the rate table."""
    result = rates.estimate(construction_type, site, cleaned['area'], cleaned['quality'])
    if result is None:
        return None
    return {
        'material': result['material'],
        'labour': result['labour'],
        'other': result['other'],
        'model_label': 'Rate table',
        'unit_rate': result['unit_rate'],
    }


@user_required
def predict_view(request):
    options = ml.form_options()
    sites = SiteRegion.objects.all()
    types = ConstructionType.objects.all()
    context = {
        'cities': options['city_states'],
        'qualities': options['qualities'],
        'building_types': [t for t in types if t.uses_ml],
        'infrastructure_types': [t for t in types if not t.uses_ml],
        'sites': sites,
        'values': request.POST,
    }

    if request.method == 'POST':
        construction_type = types.filter(slug=request.POST.get('btype', '')).first()
        cleaned, errors = _parse_prediction_form(request.POST, options, construction_type)
        if construction_type is None:
            errors.append('Please choose what you are building.')
        site = sites.filter(slug=request.POST.get('site', '')).first()
        if site is None:
            errors.append('Please choose a valid site location.')
        if errors:
            context['errors'] = errors
            return render(request, 'users/prediction.html', context)

        if construction_type.uses_ml:
            result = _building_estimate(cleaned, construction_type, site, options['city_states'])
        else:
            result = _infrastructure_estimate(cleaned, construction_type, site)
            if result is None:
                context['errors'] = [f'No rate has been set for {construction_type.name} on {site.name}.']
                return render(request, 'users/prediction.html', context)

        # Figures the user already knows are quotes, so they are not adjusted
        if cleaned['material_cost'] is not None:
            result['material'] = cleaned['material_cost']
        if cleaned['labor_cost'] is not None:
            result['labour'] = cleaned['labor_cost']
        total = result['material'] + result['labour'] + result['other']
        result.update(total=total, per_unit=total / cleaned['area'], site=site,
                      type=construction_type, quantity=cleaned['area'])
        if 'error_p95' in result:
            result['low'] = total * (1 - result['error_p95'] / 100)
            result['high'] = total * (1 + result['error_p95'] / 100)
        context['result'] = result
    return render(request, 'users/prediction.html', context)


@user_required
def view_dataset(request):
    df = ml.load_dataset()
    page = Paginator(df.to_dict('records'), 25).get_page(request.GET.get('page'))
    return render(request, 'users/viewdataset.html', {'page': page, 'columns': list(df.columns), 'total': len(df)})


@user_required
def rates_view(request):
    sites, rows = rates.rate_matrix()
    types = ConstructionType.objects.all()
    context = {
        'sites': sites, 'rows': rows, 'types': types,
        'qualities': list(rates.QUALITY_FACTORS),
        'values': request.GET,
    }
    if 'quantity' in request.GET:
        construction_type = types.filter(slug=request.GET.get('type', '')).first()
        site = SiteRegion.objects.filter(slug=request.GET.get('site', '')).first()
        quality = request.GET.get('quality', 'Medium')
        try:
            quantity = float(request.GET['quantity'])
        except ValueError:
            quantity = 0
        if not (construction_type and site and quality in rates.QUALITY_FACTORS and 0 < quantity < float('inf')):
            context['error'] = 'Please choose a construction type, site and quality, and enter a quantity above zero.'
        else:
            result = rates.estimate(construction_type, site, quantity, quality)
            if result is None:
                context['error'] = f'No rate has been set for {construction_type.name} on {site.name}.'
            else:
                comparison = rates.compare_sites(construction_type, quantity, quality)
                highest = max(row['total'] for row in comparison)
                for row in comparison:
                    row['width'] = round(row['total'] / highest * 100)
                context.update(result=result, chosen_type=construction_type, chosen_site=site,
                               quantity=quantity, quality=quality, comparison=comparison)
    return render(request, 'users/rates.html', context)


def _read_coordinates(params):
    try:
        lat, lng = float(params.get('lat', '')), float(params.get('lng', ''))
    except ValueError:
        return None
    return (lat, lng) if -90 <= lat <= 90 and -180 <= lng <= 180 else None


@user_required
def labour_search(request):
    trade = request.GET.get('trade', '')
    if trade not in dict(LabourContact.TRADE_CHOICES):
        trade = ''
    try:
        radius = int(request.GET.get('radius', 50))
    except ValueError:
        radius = 50
    if radius not in RADIUS_CHOICES:
        radius = 50
    available_only = request.GET.get('available') == 'on'
    location = request.GET.get('location', '').strip()

    context = {
        'trades': LabourContact.TRADE_CHOICES, 'radius_choices': RADIUS_CHOICES,
        'trade': trade, 'radius': radius, 'available_only': available_only, 'location': location,
    }
    coords = _read_coordinates(request.GET)
    if coords is None and location:
        coords = labour.resolve_location(location)
        if coords is None:
            context['error'] = f'We could not find "{location}". Check the spelling or try a nearby city.'
    elif coords is None and 'location' in request.GET:
        context['error'] = 'Enter a location or use your current location.'

    if coords:
        results = labour.search_labour(*coords, trade, radius, available_only)
        context.update(searched=True, results=results, lat=coords[0], lng=coords[1],
                       has_samples=any(w.is_sample for w in results))
        if not results:
            context['nearest'] = labour.nearest_labour(*coords, trade, available_only)
    return render(request, 'users/labour_search.html', context)


@require_GET
@user_required_json
def labour_osm(request):
    coords = _read_coordinates(request.GET)
    if coords is None:
        return JsonResponse({'error': 'Invalid location.'}, status=400)
    trade = request.GET.get('trade', '')
    try:
        radius = min(int(request.GET.get('radius', 50)), labour.OSM_MAX_RADIUS_KM)
        places = labour.search_openstreetmap(*coords, trade, radius)
    except ValueError:
        return JsonResponse({'error': 'Invalid search.'}, status=400)
    except requests.RequestException:
        return JsonResponse({'error': 'OpenStreetMap is busy right now. Please try again shortly.'}, status=503)
    return JsonResponse({'places': places, 'radius': radius})


def labour_register(request):
    form = LabourForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Thank you! The listing will appear in search once an admin approves it.')
        return redirect('labour_register')
    return render(request, 'labour_register.html', {'form': form})


@user_required
def chatbot_view(request):
    return render(request, 'chatbot.html')


@require_GET
@user_required_json
def chatbot_response(request):
    message = request.GET.get('message', '').strip()[:MAX_CHAT_MESSAGE]
    if not message:
        return JsonResponse({'response': 'Please type a question.'})
    return JsonResponse({'response': chatbot.respond(request, message)})
