from os import environ


SESSION_CONFIGS = [
    {
        'name': 'treasure_hunters',
        'display_name': "Treasure Hunters",
        'num_demo_participants': 2,
        'app_sequence': ['treasure_hunters'],
        'treatment_manual': False, # For admin to enter manually
        'treatment': False, # For admin to enter manually
        'session_id': '', # For admin to enter manually
        'sequence_manual': False, # For admin to enter manually
        'sequence': '' # For admin to enter manually
    }
]

ROOMS = [
    dict(
        name='lab',
        display_name='Main Lab Room',
        participant_label_file='terminals.txt',
        use_secure_urls=True,  # recommended to prevent tampering
    ),
]

INSTALLED_APPS = ['otree', 'treasure_hunters']

# if you set a property in SESSION_CONFIG_DEFAULTS, it will be inherited by all configs
# in SESSION_CONFIGS, except those that explicitly override it.
# the session config can be accessed from methods in your apps as self.session.config,
# e.g. self.session.config['participation_fee']

SESSION_CONFIG_DEFAULTS = dict(
    real_world_currency_per_point=1.00, participation_fee=0.00, doc=""
)

DEBUG = 0

PARTICIPANT_FIELDS = []
SESSION_FIELDS = []

# ISO-639 code
# for example: de, fr, ja, ko, zh-hans
LANGUAGE_CODE = 'en'

# e.g. EUR, GBP, CNY, JPY
REAL_WORLD_CURRENCY_CODE = 'USD'
USE_POINTS = True

ADMIN_USERNAME = 'admin'
# for security, best to set admin password in an environment variable
ADMIN_PASSWORD = environ.get('OTREE_ADMIN_PASSWORD')

DEMO_PAGE_INTRO_HTML = """ """

# Set this in the server environment; never commit the value.
SECRET_KEY = environ['OTREE_SECRET_KEY']
OTREE_REST_KEY = environ.get("OTREE_REST_KEY")

ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'treasurehunters.local']