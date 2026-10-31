from django.contrib import admin

from .models import ConstructionRate, ConstructionType, LabourContact, SiteRegion, UserRegistrationModel

admin.site.register(ConstructionType)
admin.site.register(SiteRegion)
admin.site.register(ConstructionRate)
admin.site.register(LabourContact)


@admin.register(UserRegistrationModel)
class UserRegistrationAdmin(admin.ModelAdmin):
    list_display = ('name', 'loginid', 'email', 'status')
    exclude = ('password',)
