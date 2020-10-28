from typing import List

from django.conf import settings
from django.db.models import Q
from django.dispatch import receiver
from netaddr import IPAddress

from adminapi.dataset import MultiAttr
from serveradmin.dataset import Query, DatasetObject
from serveradmin.powerdns.models import Record, Domain
from serveradmin.serverdb.query_committer import post_commit

config = settings.POWERDNS['record']
SERVERTYPE = config['servertype']
TTL = config['ttl']
RELATED_BY = config['related_by']
MAPPING = config['attributes']
ATTRS = list(MAPPING.values())
DOMAIN = settings.POWERDNS['domain']['related_by']
SOA = settings.POWERDNS['domain']['soa']

RESTRICT_RECORD = ['servertype', 'hostname', TTL, {DOMAIN: [SOA]}, *ATTRS]
RESTRICT_OBJECT = [
    'servertype', 'hostname', {RELATED_BY: RESTRICT_RECORD}] + ATTRS
RESTRICT_ALL = [
    'object_id', 'hostname', 'servertype', *ATTRS, TTL,
    {DOMAIN: ['object_id']}, {RELATED_BY: RESTRICT_RECORD}]


@receiver(post_commit)
def apply_record_changes(sender, **kwargs):
    """Apply object changes to PowerDNS records

    Check for changes relevant for PowerDNS records and apply them.

    :param sender:
    :param kwargs:
    :return:
    """

    if kwargs['created']:
        for created in kwargs['created']:
            _create_records(created)
    if kwargs['deleted']:
        _delete_records(kwargs['deleted'])


def _create_records(created: dict) -> None:
    """Create PowerDNS records for a new Serveradmin object

    Create PowerDNS records for new Serveradmin objects of servertype record
    and all others with an attribute relating to one or more records.

    :param created: One created object emitted by post_commit signal
    :return:
    """

    hostname = created['hostname']

    if created['servertype'] == SERVERTYPE:
        record = Query({'hostname': hostname}, RESTRICT_RECORD).get()
        domain = Domain.objects.get(id=record[DOMAIN]['object_id'])
        _create_pdns_records(domain, record, record)
    elif RELATED_BY in created:
        s_object = Query({'hostname': hostname}, RESTRICT_OBJECT).get()
        for record in s_object[RELATED_BY]:
            domain = Domain.objects.get(id=record[DOMAIN]['object_id'])
            _create_pdns_records(domain, s_object, record)


def _create_pdns_records(
    domain: Domain, s_object: DatasetObject, record: DatasetObject
) -> None:
    """Create PowerDNS records for mapped attributes

    :param domain: PowerDNS domain object
    :param s_object: Serveradmin object
    :param record: Serveradmin record object for s_object
    :return:
    """

    for record_type, attribute in MAPPING.items():
        if attribute not in s_object:
            continue

        if type(s_object[attribute]) == MultiAttr:
            values = {str(value) for value in s_object[attribute]}
        else:
            # Empty values resolves to attribute not set
            if not s_object[attribute]:
                continue
            else:
                values = {str(s_object[attribute])}

        # Delete PowerDNS records for record for object overrides
        if len(values) and s_object['servertype'] != SERVERTYPE:
            Record.objects.filter(
                record_id=record['object_id'],
                object_id=record['object_id'],
                type=record_type).delete()

        for value in values:
            _create_pdns_records_in_db(
                domain,
                record['hostname'],
                record_type,
                record[TTL],
                value,
                s_object['object_id'],
                record['object_id'],
                record['hostname'],
                record[DOMAIN][SOA])


def _create_pdns_records_in_db(
        domain: Domain,
        name: str,
        record_type: str,
        ttl: int,
        content: str,
        object_id: int,
        record_id: int,
        record_name: str = None,
        soa: str = None,
) -> None:
    """Create PowerDNS records in DB

    :param domain:
    :param name:
    :param record_type:
    :param ttl:
    :param content:
    :param object_id:
    :param record_id:
    :param record_name:
    :param soa:
    :return:
    """

    Record.objects.create(
        domain=domain,
        name=name,
        type=record_type,
        ttl=ttl,
        content=content,
        record_id=record_id,
        object_id=object_id)

    # Create PTR records for A and AAAA DNS records
    if record_type in ('A', 'AAAA'):
        Record.objects.create(
            domain=domain,
            name=IPAddress(content).reverse_dns[:-1],
            type='SOA',
            ttl=ttl,
            content=soa,
            record_id=record_id,
            object_id=object_id)
        Record.objects.create(
            domain=domain,
            name=IPAddress(content).reverse_dns[:-1],
            type='PTR',
            ttl=ttl,
            content=record_name,
            record_id=record_id,
            object_id=object_id)


def _delete_records(deleted: List[int]) -> None:
    """Delete PowerDNS records for deleted objects

    Delete PowerDNS records for Serveradmin objects of servertype record and
    all others with an attribute relating to one or more records.

    :param deleted: List of object_ids
    :return:
    """

    records = Record.objects.filter(
        Q(object_id__in=deleted) |
        Q(record_id__in=deleted)).only('object_id', 'record_id')

    for record in records:
        # Restore records from overrides of object if not deleted too
        if (
                record.object_id != record.record_id and
                record.record_id not in deleted
        ):
            s_object = Query(
                {'object_id': record.record_id}, RESTRICT_RECORD).get()
            domain = Domain.objects.get(id=s_object[DOMAIN]['object_id'])
            _create_pdns_records(domain, s_object, s_object)

    records.delete()
