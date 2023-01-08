from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'your.domain.name',
]

# Leave this as true during development, so that you get error pages describing what went wrong.
DEBUG = True

# You can add your e-mail if you want to receive notifications of failures I think, but its probably not a good idea.
ADMINS = [
    # ('Your Name', 'your_email@example.com'),
]

# You can also make local sqlite databases in your current directory
# if you want to test changes to the data model
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'ATOMIC_REQUESTS': True,
    },
}

# django-allauth social account provider settings.  For this app, we're just using Discord but you can add others.
SOCIALACCOUNT_PROVIDERS = {
    'discord': {
        'APP': {
            'client_id': 'YOUR CLIENT ID',
            'secret': 'YOUR SECRET',
            'key': 'YOUR PRIVATE KEY',
        },
        'SCOPE': [
            'identify',
        ],
        # Add discord uids that are allowed to log in here.
        'ALLOWED_UIDS': [],

        # Add uids here that should be marked as staff and/or superusers.
        'STAFF_UIDS': [],
        'SUPERUSER_UIDS': [],
    }
}

TIME_ZONE = 'America/Toronto'

SECRET_KEY = 'django-insecure-!)wo&dc0(r$a1w5)km^dvd#i7tm!%ympj(8dtcmtt7)*%9d_!6'

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / 'static'

MEDIA_URL = 'media/'
MEDIA_ROOT = '/srv/cardconjurer'

# Add the path to your static CardConjurer HTML folder here!!!
CARDCONJURER_ROOT = ''
