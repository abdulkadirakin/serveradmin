from time import time
from typing import List

from django.conf import settings
from django.db.models import Q
from django.dispatch import receiver
from netaddr import IPAddress

from adminapi.dataset import MultiAttr
from adminapi.filters import Any
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
    if kwargs['changed']:
        for changed in kwargs['changed']:
            _update_records(changed)
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


def _update_records(changed: dict) -> None:
    # Avoid querying Serveradmin object multiple times for the same change
    obj = None

    if 'hostname' in changed:
        _update_records_for_hostname(
            changed['object_id'], changed['hostname']['new'])

    if TTL in changed:
        Record.objects.filter(record_id=changed['object_id']).update(
            ttl=changed[TTL]['new'], change_date=int(time()))

    for attr in changed.keys():
        if attr in ATTRS:
            record_type = [a for a, v in MAPPING.items() if v == attr][0]
            if obj is None:
                obj = Query(
                    {'object_id': changed['object_id']}, RESTRICT_ALL).get()

            if RELATED_BY in obj:
                for record in obj['records']:
                    _update_records_for_attribute(
                        record, obj, changed, attr, record_type)
            elif obj['servertype'] == SERVERTYPE:
                _update_records_for_attribute(
                    obj, obj, changed, attr, record_type)
            else:
                # Not a record servertype nor an object relating to a
                # record - nothing to do.
                break

    # Remove all records for objects where the relation to a record has
    # been removed and create records for those added.
    if RELATED_BY in changed:
        record_ids = [o['object_id'] for o in Query(
            {'hostname': Any(*changed[RELATED_BY]['remove'])})]
        Record.objects.filter(
            record_id__in=record_ids,
            object_id=changed['object_id']).delete()

        if changed[RELATED_BY]['add']:
            _create_records_for_object(
                object_id=changed['object_id'],
                records_filter=changed[RELATED_BY]['add'])


def _update_records_for_hostname(object_id: int, new_hostname: str) -> None:
    Record.objects.filter(
        Q(record_id=object_id) & ~Q(type__in=('SOA', 'PTR'))
    ).update(name=new_hostname, change_date=int(time()))

    Record.objects.filter(record_id=object_id, type='PTR').update(
        content=new_hostname, change_date=int(time()))


def _update_records_for_attribute(
        record: DatasetObject,
        obj: DatasetObject,
        change: dict,
        attr: str,
        record_type: str
) -> None:
    domain = Domain.objects.get(id=record[DOMAIN]['object_id'])

    if change[attr]['action'] == 'update':
        _update_records_for_single_attribute(
            domain, record, obj, change, attr, record_type)
    elif change[attr]['action'] == 'multi':
        _update_records_for_multi_attribute(
            domain, record, obj, change, attr, record_type)


def _update_records_for_single_attribute(
        domain: Domain,
        record_obj: DatasetObject,
        obj: DatasetObject,
        change: dict,
        attr: str,
        record_type: str,
) -> None:
    if change[attr]['new'] is None:
        # Restore records from the record object if needed
        if obj['servertype'] != SERVERTYPE and attr in record_obj:
            Record.objects.create(
                object_id=record_obj['object_id'],
                record_id=record_obj['object_id'],
                type=record_type,
                content=record_obj[attr],
                name=record_obj['hostname'],
                ttl=record_obj['ttl'])

        # Remove all records previously created for the object or record
        return Record.objects.filter(
            object_id=obj['object_id'],
            record_id=record_obj['object_id'],
            type=record_type,
            content=change[attr]['old']
        ).delete()

    record, created = Record.objects.get_or_create(
        object_id=obj['object_id'],
        record_id=record_obj['object_id'],
        type=record_type)

    # Fill other fields
    if created:
        record.name = record_obj['hostname']
        record.ttl = record_obj[TTL]
        record.domain = domain

    record.change_date = int(time())
    record.content = str(change[attr]['new'])
    record.save()

    if record_type in ('A', 'AAAA'):
        value = str(change[attr]['new'])
        Record.objects.filter(
            object_id=obj['object_id'],
            record_id=record_obj['object_id'],
            type='SOA'
        ).update(
            name=IPAddress(value).reverse_dns[:-1], change_date=int(time()))
        Record.objects.filter(
            object_id=obj['object_id'],
            record_id=record_obj['object_id'],
            type='PTR'
        ).update(
            name=IPAddress(value).reverse_dns[:-1], change_date=int(time()))

    # Remove records from the record servertype if this is an override.
    if obj['servertype'] != SERVERTYPE:
        Record.objects.filter(
            object_id=record_obj['object_id'],
            record_id=record_obj['object_id'],
            type=record_type).delete()


def _update_records_for_multi_attribute(
        domain: Domain,
        record_obj: DatasetObject,
        obj: DatasetObject,
        change: dict,
        attr: str,
        record_type: str,
):
    if 'add' in change[attr]:
        for value in change[attr]['add']:
            Record.objects.create(
                object_id=obj['object_id'],
                record_id=record_obj['object_id'],
                type=record_type,
                content=str(value),
                name=record_obj['hostname'],
                ttl=record_obj[TTL],
                domain=domain)

            # Create PTR records for A and AAAA DNS records
            if record_type in ('A', 'AAAA'):
                Record.objects.create(
                    domain=domain,
                    name=IPAddress(value).reverse_dns[:-1],
                    type='SOA',
                    ttl=record_obj[TTL],
                    content=record_obj[DOMAIN]['soa'],
                    record_id=record_obj['object_id'],
                    object_id=obj['object_id'])
                Record.objects.create(
                    domain=domain,
                    name=IPAddress(value).reverse_dns[:-1],
                    type='PTR',
                    ttl=record_obj[TTL],
                    content=obj['hostname'],
                    record_id=record_obj['object_id'],
                    object_id=obj['object_id'])

    if 'remove' in change[attr]:
        Record.objects.filter(
            object_id=obj['object_id'],
            record_id=record_obj['object_id'],
            type=record_type,
            content__in=change[attr]['remove'],
        ).delete()

        # Remove PTR records
        if record_type in ('A', 'AAAA'):
            Record.objects.filter(
                object_id=obj['object_id'],
                record_id=record_obj['object_id'],
                type__in=('SOA', 'PTR'),
                name=IPAddress(change[attr]['remove']).reverse_dns[:-1]
            ).delete()

    # Restore records for records servertype if there is no override anymore
    if obj['servertype'] != SERVERTYPE and not obj[attr] and record_obj[attr]:
        for value in record_obj[attr]:
            Record.objects.create(
                object_id=record_obj['object_id'],
                record_id=record_obj['object_id'],
                type=record_type,
                content=str(value),
                name=record_obj['hostname'],
                ttl=record_obj['ttl'])


def _create_records_for_object(
    hostname: str = None,
    object_id: int = None,
    records_filter: List[str] = None
) -> None:
    if object_id:
        s_object = Query({'object_id': object_id}, RESTRICT_ALL).get()
    else:
        s_object = Query({'hostname': hostname}, RESTRICT_ALL).get()

    records = s_object[RELATED_BY]
    if records_filter:
        records = [r for r in records if r['hostname'] in records_filter]

    for record in records:
        domain = Domain.objects.get(id=record[DOMAIN]['object_id'])
        _create_pdns_records(domain, s_object, record)