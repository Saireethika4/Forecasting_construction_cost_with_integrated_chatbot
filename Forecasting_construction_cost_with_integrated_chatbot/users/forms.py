from django import forms
from django.contrib.auth.hashers import make_password

from .labour import resolve_location
from .models import LabourContact, UserRegistrationModel

# Vercel rejects request bodies over 4.5 MB
MAX_IMAGE_BYTES = 4 * 1024 * 1024


class UserRegistrationForm(forms.ModelForm):
    class Meta:
        model = UserRegistrationModel
        fields = ['name', 'loginid', 'email', 'password', 'mobile', 'locality', 'address', 'image']

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if UserRegistrationModel.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and image.size > MAX_IMAGE_BYTES:
            raise forms.ValidationError('Image must be 4 MB or smaller.')
        return image

    def save(self, commit=True):
        user = super().save(commit=False)
        user.password = make_password(self.cleaned_data['password'])
        user.status = 'waiting'
        if commit:
            user.save()
        return user


class LabourForm(forms.ModelForm):
    consent = forms.BooleanField(
        label='This person agrees to their phone number and details being shown to registered users',
    )

    class Meta:
        model = LabourContact
        fields = ['name', 'trade', 'phone', 'email', 'city', 'locality', 'daily_wage', 'experience_years']
        labels = {'daily_wage': 'Daily wage (₹)', 'experience_years': 'Years of experience', 'phone': 'Mobile number'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != 'consent':
                field.widget.attrs['class'] = 'form-select' if name == 'trade' else 'form-control'

    def clean(self):
        cleaned = super().clean()
        city = cleaned.get('city')
        if city:
            coords = resolve_location(city)
            if coords is None:
                self.add_error('city', 'We could not find this place. Check the spelling or try a nearby city.')
            else:
                self.instance.latitude, self.instance.longitude = coords
        return cleaned
