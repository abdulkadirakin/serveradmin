from django.conf import settings
from django.dispatch import receiver

from serveradmin.serverdb.query_committer import post_commit

config = settings.POWERDNS['record']
SERVERTYPE = config['servertype']
TTL = config['ttl']
RELATED_BY = config['related_by']
ATTRS = config['attributes']


@receiver(post_commit)
def apply_record_changes(sender, **kwargs):
    """Apply record changes to PowerDNS

    Listen to changes relevant for records and apply them also to PowerDNS
    if necessary.

    :param sender:
    :param kwargs:
    :return:
    """
    pass