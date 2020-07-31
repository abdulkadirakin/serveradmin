from serveradmin.dataset import Query
from serveradmin.powerdns.models import Record
from serveradmin.powerdns.tests.base import PowerDNSTests, create_object
from serveradmin.serverdb.query_committer import CommitError


class PowerDNSRecordDeletionTests(PowerDNSTests):
    """Test cases for PowerDNS record deletion

    This class covers test cases to ensure the desired behaviour for PowerDNS
    records deleted by Serveradmin.
    """

    def test_object_deletion_removes_records(self):
        """Test deletion of a object removes matching records

        When deleting any object of any servertype with `records` attribute
        set, records related to this object must be removed.
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name)
        record_name = record.get()['hostname']
        vm = create_object('vm', records={record_name}, intern_ip=self.a,
                           ipv6=self.aaaa)
        object_id = vm.get()['object_id']

        records = Record.objects.filter(object_id=object_id)
        num_records = records.count()

        # Ensure records exist before
        self.assertGreater(num_records, 0, 'Missing records')

        # Delete object
        vms = Query({'object_id': object_id})
        vms.delete()
        vms.commit(user=self.user)

        # Ensure records have been removed
        self.assertEqual(records.count(), num_records - num_records,
                         'Records not removed')

    def test_object_deletion_restores_record_values(self):
        """Test deletion of an override restores record values

        When deleting any object of any servertype with `records` attribute
        set, a single or multi attribute (with value) mapped in attribute list
        and a record with the same single or multi attribute (with value)
        mapped in attribute list, the record for the object must be removed
        and a value from the record must be created again.
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name, mx=self.mx)
        record_name = record.get()['hostname']
        record_id = record.get()['object_id']
        container = create_object('container', records={record_name},
                                  mx=self.mx)
        object_id = container.get()['object_id']

        mx_record = Record.objects.filter(object_id=record_id, type='MX',
                                          content=self.mx)

        # Ensure record does not exist before
        self.assertFalse(mx_record.exists(), 'Extra MX record found')

        # Delete object
        containers = Query({'object_id': object_id})
        containers.delete()
        containers.commit(user=self.user)

        # Ensure MX record from record object have been restored
        self.assertTrue(mx_record.exists(), 'MX record not created')

    def test_record_deletion_removes_records(self):
        """Test deletion of a record removes matching records

        When deleting a record, records related to this object must be removed.
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name, mx=self.mx)
        record_id = record.get()['object_id']

        records = Record.objects.filter(record_id=record_id)

        # Check if records exist before
        self.assertGreater(records.count(), 0, 'Missing records')

        # Delete record object
        r = Query({'object_id': record_id})
        r.delete()
        r.commit(user=self.user)

        # Make sure records have been deleted
        self.assertEqual(records.count(), 0, 'Records not deleted')

    def test_record_deletion_with_related_objects_is_impossible(self):
        """Test deletion of a related record is not possible

        When trying to remove a record object that is still related by one
        or more objects via `records` attribute this must fail. This is a
        behaviour of Serveradmin relation attributes and should therefore not
        be covered by tests but in case Serveradmin behaviour changes or has
        a bug, this would make it visible.
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name)
        record_name = record.get()['hostname']
        create_object('vm', records={record_name}, intern_ip=self.a)

        msg = 'Cannot delete servers because they are referenced by .*'
        with self.assertRaisesRegex(CommitError, msg):
            r = Query({'hostname': record_name})
            r.delete()
            r.commit(user=self.user)

    def test_domain_deletion_with_related_records_is_impossible(self):
        """Test deletion of a related domain is not possible

        Same as test_record_deletion_with_related_objects_is_impossible but
        for the domain servertype.
        """

        domain_name = create_object('domain').get()['hostname']
        create_object('record', domain=domain_name)

        msg = 'Cannot delete servers because they are referenced by .*'
        with self.assertRaisesRegex(CommitError, msg):
            d = Query({'hostname': domain_name})
            d.delete()
            d.commit(user=self.user)
