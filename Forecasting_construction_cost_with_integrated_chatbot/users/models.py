from django.core.validators import EmailValidator, MinValueValidator, RegexValidator
from django.db import models

mobile_validator = RegexValidator(regex=r'^[56789][0-9]{9}$', message='Mobile must start with 5, 6, 7, 8, or 9 and be 10 digits long')


class UserRegistrationModel(models.Model):
    # Validators
    name_validator = RegexValidator(regex=r"^[a-zA-Z][a-zA-Z .'-]*$", message='Name must contain only letters, spaces and . \' -')
    loginid_validator = RegexValidator(regex=r'^[a-zA-Z0-9_.]+$', message='Login ID must contain only letters, numbers, _ and .')
    password_validator = RegexValidator(
        regex=r'(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).{8,}',
        message='Password must contain at least one number, one uppercase, one lowercase letter, and at least 8 characters'
    )
    email_validator = EmailValidator(message='Enter a valid email address')

    # Fields with validation
    name = models.CharField(max_length=100, validators=[name_validator])
    loginid = models.CharField(max_length=100, unique=True, validators=[loginid_validator])
    # Holds a Django password hash; the validator checks the raw password at registration
    password = models.CharField(max_length=128, validators=[password_validator])
    mobile = models.CharField(max_length=10, validators=[mobile_validator])
    email = models.EmailField(max_length=100, unique=True, validators=[email_validator])
    locality = models.CharField(max_length=100)
    address = models.TextField(max_length=250)
    status = models.CharField(max_length=100, default='waiting')
    image = models.ImageField(upload_to='user_images/', null=True, blank=True)

    def __str__(self):
        return self.name


class ConstructionType(models.Model):
    """What is being built, e.g. a bridge, and the unit it is priced in."""
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=60)
    unit = models.CharField(max_length=30, help_text='Pricing unit, e.g. sq.ft or sq.m of deck')
    keywords = models.CharField(max_length=120, blank=True, help_text='Comma-separated words the chatbot recognises')
    material_pct = models.PositiveSmallIntegerField(default=60)
    labour_pct = models.PositiveSmallIntegerField(default=25)
    ml_building_type = models.CharField(
        max_length=20, blank=True,
        help_text='Dataset building type the ML model uses for this, or blank to price from the rate table only',
    )
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return self.name

    @property
    def uses_ml(self):
        return bool(self.ml_building_type)

    @property
    def other_pct(self):
        return max(0, 100 - self.material_pct - self.labour_pct)


class SiteRegion(models.Model):
    """Where it is being built, e.g. a hill station or a water body."""
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=200, blank=True, help_text='Why this site changes the cost')
    keywords = models.CharField(max_length=120, blank=True, help_text='Comma-separated words the chatbot recognises')
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return self.name


class ConstructionRate(models.Model):
    """Rate in rupees per unit for one construction type on one site, at Medium quality."""
    construction_type = models.ForeignKey(ConstructionType, on_delete=models.CASCADE, related_name='rates')
    site = models.ForeignKey(SiteRegion, on_delete=models.CASCADE, related_name='rates')
    rate = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(1)])

    class Meta:
        unique_together = ('construction_type', 'site')

    def __str__(self):
        return f'{self.construction_type} on {self.site}: {self.rate}'


class LabourContact(models.Model):
    """A worker or contractor listed in the directory, shown only once approved."""
    TRADE_CHOICES = [
        ('mason', 'Mason'),
        ('carpenter', 'Carpenter'),
        ('electrician', 'Electrician'),
        ('plumber', 'Plumber'),
        ('painter', 'Painter'),
        ('bar_bender', 'Bar Bender'),
        ('welder', 'Welder'),
        ('tiler', 'Tile Layer'),
        ('helper', 'General Labour / Helper'),
        ('contractor', 'Labour Contractor'),
    ]
    PENDING, APPROVED = 'pending', 'approved'
    STATUS_CHOICES = [(PENDING, 'Pending approval'), (APPROVED, 'Approved')]

    name = models.CharField(max_length=100)
    trade = models.CharField(max_length=20, choices=TRADE_CHOICES)
    phone = models.CharField(max_length=10, validators=[mobile_validator])
    email = models.EmailField(max_length=100, blank=True)
    city = models.CharField(max_length=100)
    locality = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    daily_wage = models.PositiveIntegerField(null=True, blank=True, help_text='Rupees per day')
    experience_years = models.PositiveSmallIntegerField(default=0)
    is_available = models.BooleanField(default=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    is_sample = models.BooleanField(default=False, help_text='Placeholder demo record, not a real person')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.get_trade_display()}, {self.city})'
