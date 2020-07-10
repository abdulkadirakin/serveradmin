from django.conf import settings
from django.dispatch import receiver

from serveradmin.serverdb.query_committer import post_commit

config = settings.POWERDNS['domain']
SERVERTYPE = config['servertype']
TYPE = config['type']
RELATED_BY = config['related_by']
SOA = config['soa']
NS = config['ns']


@receiver(post_commit)
def apply_domain_changes(sender, **kwargs):
    """Apply domain changes to PowerDNS

    Listen to changes relevant for domains and apply them also to PowerDNS
    if necessary.

    :param sender:
    :param kwargs:
    :return:
    """
    pass
