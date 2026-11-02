from decimal import Decimal, InvalidOperation
from functools import wraps
from hmac import compare_digest

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from users.forms import LabourForm
from users.models import ConstructionRate, LabourContact, UserRegistrationModel
from users.rates import rate_matrix


def admin_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('is_admin'):
            messages.warning(request, 'Please log in as admin to continue.')
            return redirect('AdminLoginCheck')
        return view(request, *args, **kwargs)
    return wrapper


# Admin login check function
def adminLoginCheck(request):
    if request.method == 'POST':
        usrid = request.POST.get('loginid', '')
        pswd = request.POST.get('password', '')

        if compare_digest(usrid.encode(), settings.ADMIN_LOGIN.encode()) and compare_digest(pswd.encode(), settings.ADMIN_PASSWORD.encode()):
            request.session.cycle_key()
            request.session['is_admin'] = True
            return redirect('AdminHome')
        messages.error(request, 'Please check your login details.')
        return redirect('AdminLoginCheck')

    return render(request, 'adminlogin.html')


# Admin home page
@admin_required
def adminHome(request):
    users = UserRegistrationModel.objects
    labour = LabourContact.objects
    return render(request, 'admins/adminHome.html', {
        'total_users': users.count(),
        'waiting_users': users.filter(status='waiting').count(),
        'labour_listed': labour.filter(status=LabourContact.APPROVED).count(),
        'labour_pending': labour.filter(status=LabourContact.PENDING).count(),
        'rate_count': ConstructionRate.objects.count(),
    })


# View all registered users
@admin_required
def RegisterUsersView(request):
    data = UserRegistrationModel.objects.all()
    return render(request, 'admins/viewregisterusers.html', {'data': data})


@admin_required
@require_POST
def activateUser(request, id):
    UserRegistrationModel.objects.filter(id=id).update(status='active')
    return redirect('RegisterUsersView')


@admin_required
@require_POST
def deactivateUser(request, id):
    UserRegistrationModel.objects.filter(id=id).update(status='deactivated')
    return redirect('RegisterUsersView')


@admin_required
@require_POST
def deleteUser(request, id):
    for user in UserRegistrationModel.objects.filter(id=id):
        # Stored photos are served publicly, so they must go with the account
        if user.image:
            user.image.delete(save=False)
        user.delete()
    return redirect('RegisterUsersView')


@admin_required
def manageRates(request):
    if request.method == 'POST':
        updates = []
        for rate in ConstructionRate.objects.all():
            raw = request.POST.get(f'rate_{rate.id}', '')
            try:
                value = Decimal(raw)
                if not value.is_finite() or not 1 <= value < Decimal('1e12'):
                    raise InvalidOperation
            except InvalidOperation:
                messages.error(request, f'Rates must be numbers of at least 1. Check {rate.construction_type} on {rate.site}. Nothing was saved.')
                return redirect('manage_rates')
            rate.rate = value
            updates.append(rate)
        with transaction.atomic():
            ConstructionRate.objects.bulk_update(updates, ['rate'])
        messages.success(request, 'Rates updated.')
        return redirect('manage_rates')

    sites, rows = rate_matrix()
    return render(request, 'admins/managerates.html', {'sites': sites, 'rows': rows})


@admin_required
def manageLabour(request):
    form = LabourForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        worker = form.save(commit=False)
        worker.status = LabourContact.APPROVED
        worker.save()
        messages.success(request, f'{worker.name} added to the directory.')
        return redirect('manage_labour')
    # Pending listings first, then real ones ahead of samples
    workers = LabourContact.objects.order_by('-status', 'is_sample', '-created_at')
    page = Paginator(workers, 20).get_page(request.GET.get('page'))
    return render(request, 'admins/managelabour.html', {'form': form, 'page': page})


@admin_required
@require_POST
def labourAction(request, id, action):
    worker = LabourContact.objects.filter(id=id)
    if action == 'approve':
        worker.update(status=LabourContact.APPROVED)
    elif action == 'available':
        worker.update(is_available=True)
    elif action == 'unavailable':
        worker.update(is_available=False)
    elif action == 'delete':
        worker.delete()
    return redirect('manage_labour')
