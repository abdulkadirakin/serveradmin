SECRET_KEY = 'TEST'
LOGGING = {}
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'serveradmin',
        'OPTIONS': {
            'connect_timeout': 1,
            'client_encoding': 'UTF8',
        },
    },
    'powerdns': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'powerdns',
        'OPTIONS': {
            'connect_timeout': 1,
            'client_encoding': 'UTF8',
        },
    },
}
POWERDNS = {
    'domain': {
        'servertype': 'domain',
        'type': 'type',
        'related_by': 'domain',
        'soa': 'soa',
        'ns': 'ns',
    },
    'record': {
        'servertype': 'record',
        'ttl': 'ttl',
        'related_by': 'records',
        'attributes': {
            'A': 'intern_ip',
            'AAAA': 'ipv6',
            'MX': 'mx',
            'TXT': 'txt',
        }
    }
}