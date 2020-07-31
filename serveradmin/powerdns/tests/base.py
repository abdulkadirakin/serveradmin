import time

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TransactionTestCase

from serveradmin.dataset import Query


domain_config = settings.POWERDNS['domain']
DOMAIN_ATTR_SOA = domain_config['soa']
DOMAIN_ATTR_NS = domain_config['ns']
DOMAIN_ATTR_TYPE = domain_config['type']

record_config = settings.POWERDNS['record']
RECORD_ATTR_TTL = record_config['ttl']
RECORD_ATTRS = record_config['attributes']


def create_object(servertype: str, **kwargs) -> Query:
    obj = Query().new_object(servertype)
    obj['hostname'] = str(time.time())

    for key, value in kwargs.items():
        obj[key] = value

    obj.commit(user=User.objects.first())

    domain_attrs = [DOMAIN_ATTR_SOA, DOMAIN_ATTR_NS, DOMAIN_ATTR_TYPE]
    record_attrs = [RECORD_ATTR_TTL] + list(RECORD_ATTRS.values())
    restrict = list(
        set(['hostname'] + list(kwargs.keys()) + domain_attrs + record_attrs))

    return Query({'hostname': obj['hostname']}, restrict)


class PowerDNSTests(TransactionTestCase):
    """Base class for PowerDNS tests

    This class holds configuration used by all PowerDNS tests to avoid
    duplicated values and allow to change configuration at one point.
    """

    databases = ['default', 'powerdns']
    fixtures = ['auth.json', 'serverdb.json']

    def setUp(self) -> None:
        self.user = User.objects.first()
        self.soa = 'localhost admin@bar.com 1 900 3600 900 300'
        self.ns = {'pdns1.example.com', 'pdns2.example.com'}
        self.a = '10.0.0.1'
        self.aaaa = '2a00:1f78:fffd:4013::0001'
        self.mx = '10 mail.example.com'
        self.mx_override = '20 mail.example.com'
        self.txt = {'txt_example_1=abc', 'txt_example_2=def'}
        self.txt_override = {'txt_example_3=ghj', 'txt_example_3=klm'}
