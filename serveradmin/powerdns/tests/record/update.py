import time
from ipaddress import IPv4Address

from serveradmin.dataset import Query
from serveradmin.powerdns.models import Record
from serveradmin.powerdns.tests.base import PowerDNSTests, create_object


class PowerDNSRecordUpdateTests(PowerDNSTests):
    """Test cases for PowerDNS record updates

    This class covers test cases to ensure the desired behaviour for PowerDNS
    records being updated by Serveradmin.
    """

    def test_object_add_records_relation(self):
        """Test connecting a object to a record creates records

        When using the `records` attribute on any object of any servertype to
        point to a record all necessary records must be created.
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name)
        record_name = record.get()['hostname']

        # Create VM without records attribute set
        vm = create_object('vm', intern_ip=self.a)
        object_id = vm.get()['object_id']

        # Assert no records for this object exist
        records = Record.objects.filter(object_id=object_id)
        self.assertEqual(records.count(), 0, 'No records should exist')

        # Update records relation attribute
        vms = Query({'object_id': object_id}, ['records'])
        vms.update(records={record_name})
        vms.commit(user=self.user)

        # Test records have been created
        Record.objects.filter(object_id=object_id)
        self.assertGreater(records.count(), 0, 'Missing records for object')

    def test_object_remove_records_relation(self):
        """Test removing a record relation removes records

        When removing the relation to a record by removing a record from the
        `records` attribute on any object of any servertype all existing
        records must be removed.
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name)
        record_name = record.get()['hostname']
        vm = create_object(
            'vm', intern_ip=self.a, txt=self.txt, records={record_name})
        object_id = vm.get()['object_id']

        records = Record.objects.filter(object_id=object_id)

        # Ensure records exist before, 1x AAAA, 2x TXT
        self.assertGreaterEqual(records.count(), 3, 'Too few records exist')

        # Remove relation to record from object
        vms = Query({'object_id': object_id}, ['records'])
        vms.get()['records'].remove(record_name)
        vms.commit(user=self.user)

        # Check records for object have been removed
        records = Record.objects.filter(object_id=object_id)
        self.assertEqual(records.count(), 0, 'Records for object not removed')

    def test_object_attribute_add_overrides_record_attribute(self):
        """Test object attribute overrides record attributes

        When setting a value for a mapped single or multi attribute
        (with values) on any object of any servertype with the `records`
        attribute set that has already the same attribute set at the related
        record object in Serveradmin the existing records must be removed and
        new ones created for the object.
        """

        # Create a record with a mapped MX attribute
        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', mx=self.mx, domain=domain_name)
        record_id = record.get()['object_id']
        record_name = record.get()['hostname']
        container = create_object('container', records={record_name})

        # Make sure it creates an MX record
        mx_record = Record.objects.filter(object_id=record_id, type='MX')
        self.assertEqual(mx_record.count(), 1, 'No MX record found')
        self.assertEqual(
            mx_record.get().content, self.mx, 'Wrong content at record')

        # Create an MX override with a VM object
        mx_override = '10 override.example.com'
        containers = Query({'object_id': container.get()['object_id']}, ['mx'])
        containers.update(mx=mx_override)
        containers.commit(user=self.user)

        # Assert MX record from record object has been removed
        mx_record = Record.objects.filter(object_id=record_id, type='MX')
        self.assertEqual(mx_record.count(), 0, 'MX record not removed')

        # Assert new MX record from object has been created
        object_id = container.get()['object_id']
        new_mx_record = Record.objects.filter(object_id=object_id, type='MX')
        self.assertEqual(new_mx_record.count(), 1, 'No MX record found')
        self.assertEqual(new_mx_record.get().content, mx_override,
                         'Wrong content for MX record')

    def test_object_single_attribute_remove_restores_record_attribute(self):
        """Test removal of object attribute restores record

        When removing the value of a single attribute of an object the value
        of the record with a value for this single attribute must be restored.
        """

        # Create a record and object with override
        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', mx=self.mx, domain=domain_name)
        record_name = record.get()['hostname']
        mx_override = '10 override.example.com'
        container = create_object(
            'container', records={record_name}, mx=mx_override)
        object_id = container.get()['object_id']

        # Check MX record is from the object and not from record
        mx_record = Record.objects.filter(object_id=object_id, type='MX')
        self.assertEqual(mx_record.count(), 1, 'No MX record found')
        self.assertEqual(mx_record.get().content, mx_override,
                         'Wrong content for record')

        # Remove override from object
        containers = Query({'object_id': object_id}, ['mx'])
        containers.get()['mx'] = None
        containers.commit(user=self.user)

        # Ensure object record has been removed
        mx_record = Record.objects.filter(object_id=object_id, type='MX')
        self.assertEqual(mx_record.count(), 0, 'MX record not removed')

        # Ensure record has been restored
        record_id = record.get()['object_id']
        new_mx_record = Record.objects.filter(object_id=record_id, type='MX')
        self.assertEqual(new_mx_record.count(), 1, 'No MX record found')
        self.assertEqual(new_mx_record.get().content, self.mx,
                         'Wrong content for MX record')

    def test_object_multi_attribute_remove_restores_record_attribute(self):
        # Create a record and object with override
        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', txt=self.txt, domain=domain_name)
        record_name = record.get()['hostname']
        txt_override = {'txt_override=1', 'another_one=2'}
        container = create_object(
            'container', records={record_name}, txt=txt_override)
        object_id = container.get()['object_id']

        # Check TXT record is from the object and not from record
        txt_records = Record.objects.filter(object_id=object_id, type='TXT')
        self.assertEqual(txt_records.count(), 2, 'Not enough TXT records')
        for txt_record in txt_records:
            self.assertIn(txt_record.content, txt_override, 'Wrong TXT record')

        # Remove override from object
        containers = Query({'object_id': object_id}, ['txt'])
        containers.update(txt=set())
        containers.commit(user=self.user)

        # Ensure object record has been removed
        txt_records = Record.objects.filter(object_id=object_id, type='TXT')
        self.assertEqual(txt_records.count(), 0, 'TXT records not removed')

        # Ensure values from record has been restored
        record_id = record.get()['object_id']
        new_txt_records = Record.objects.filter(object_id=record_id, type='TXT')
        self.assertEqual(new_txt_records.count(), 2, 'Too few TXT records')
        for txt_record in new_txt_records:
            self.assertIn(txt_record.content, self.txt, 'Wrong TXT record')

    def test_record_update_attribute_add_for_single_attribute(self):
        """Test setting a attribute value creates a new record

        When setting a initial value for a mapped single attribute to an
        existing object of servertype record a new record must be created with
        the value as content.
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name)
        record_id = record.get()['object_id']

        records = Record.objects.filter(object_id=record_id, type='MX')

        self.assertEqual(records.count(), 0, 'Too many MX records')

        mx_value = '10 record-mx.example.com'
        r = Query({'object_id': record_id}, ['mx'])
        r.update(mx=mx_value)
        r.commit(user=self.user)

        records = Record.objects.filter(object_id=record_id, type='MX')
        self.assertEqual(records.count(), 1, 'Wrong number of MX records')
        self.assertEqual(records.get().content, mx_value, 'Wrong content')

    def test_record_update_attribute_change_for_single_attribute(self):
        """Test attribute changes are applied to the record

        When updating mapped single attributes of a record object the change
        must be applied to the record(s).
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name, mx=self.mx)
        record_id = record.get()['object_id']

        records = Record.objects.filter(object_id=record_id, type='MX')

        self.assertEqual(records.count(), 1, 'Wrong number of MX records')
        self.assertEqual(records.get().content, self.mx, 'Wrong content')

        new_mx_value = '10 update-mx.example.com'
        r = Query({'object_id': record_id}, ['mx'])
        r.update(mx=new_mx_value)
        r.commit(user=self.user)

        records = Record.objects.filter(object_id=record_id, type='MX')
        self.assertEqual(records.count(), 1, 'Wrong number of MX records')
        self.assertEqual(records.get().content, new_mx_value, 'Wrong content')

    def test_record_update_attribute_remove_for_single_attribute(self):
        """Test removal of an attribute value removes the record

        When removing the value for a mapped single attribute to an existing
        object of servertype record the matching record must be removed.
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name, mx=self.mx)
        record_id = record.get()['object_id']

        records = Record.objects.filter(object_id=record_id, type='MX')

        # Check MX record exist before
        self.assertEqual(records.count(), 1, 'Wrong number of records')

        # Delete MX record value
        r = Query({'object_id': record_id}, ['mx'])
        r.update(mx=None)
        r.commit(user=self.user)

        # Make sure MX record has been removed
        records = Record.objects.filter(object_id=record_id, type='MX')
        self.assertEqual(records.count(), 0, 'Records not deleted')

    def test_record_update_attribute_add_for_multi_attribute(self):
        """Test adding a attribute value creates new record(s)

        When adding a value to a mapped multi attribute of a record object a
        new record must be created.
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name)
        record_id = record.get()['object_id']

        # Check no records exist before
        records = Record.objects.filter(object_id=record_id, type='TXT')
        self.assertEqual(records.count(), 0, 'Too many records exist')

        # Add new TXT record value
        new_txt_record = 'new_txt_record=260'
        r = Query({'object_id': record_id}, ['txt'])
        r.get()['txt'].add(new_txt_record)
        r.commit(user=self.user)

        records = Record.objects.filter(object_id=record_id, type='TXT')
        self.assertEqual(records.count(), 1, 'Missing new TXT record')
        self.assertEqual(records.get().content, new_txt_record,
                         'Wrong content for TXT record')

    def test_record_update_attribute_remove_for_multi_attribute(self):
        """Test removing a attribute value removes record(s)

        When removing a value from a mapped multi attribute of a record object
        the existing records are removed.
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name, txt=self.txt)
        object_id = record.get()['object_id']
        txt_remove = 'txt_example_1=abc'

        # Test records exist before
        records = Record.objects.filter(
            object_id=object_id, type='TXT', content=txt_remove)
        self.assertTrue(records.exists(), 'TXT record does not exist')

        # Remove TXT record
        q_records = Query({'object_id': object_id}, ['txt'])
        q_records.get()['txt'].remove(txt_remove)
        q_records.commit(user=self.user)

        # Check removal
        records = Record.objects.filter(
            object_id=object_id, type='TXT', content=txt_remove)
        self.assertFalse(records.exists(), 'TXT record not removed')

    def test_object_update_attribute_add_for_single_attribute(self):
        """Test setting a attribute value creates new record(s)

        When setting a initial value for a mapped single attribute of any
        object of any servertype with a related record using the `records`
        attribute the necessary records must be created.
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name)
        record_name = record.get()['hostname']
        vm = create_object('vm', records={record_name}, intern_ip=self.a)
        object_id = vm.get()['object_id']
        mx_content = '10 override.example.com'

        # Ensure no record exists before
        mx_record = Record.objects.filter(
            object_id=object_id, type='MX', content=mx_content)
        self.assertFalse(mx_record.exists(), 'Found extra MX record')

        # Add value for single attribute
        vms = Query({'object_id': object_id}, ['mx'])
        vms.update(mx=mx_content)
        vms.commit(user=self.user)

        # Check record has been create for object
        mx_record = Record.objects.filter(
            object_id=object_id, type='MX', content=mx_content)
        self.assertTrue(mx_record.exists(), 'MX record not created')

    def test_object_update_attribute_change_for_single_attribute(self):
        """Test changing a attribute value updates existing records

        When changing the value for a mapped single attribute of any object
        of any servertype with a related record using the `records` attribute
        the necessary records must be updated.
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name)
        record_name = record.get()['hostname']
        vm = create_object('vm', records={record_name}, intern_ip=self.a)
        object_id = vm.get()['object_id']
        a_update = '10.0.0.7'

        a_record = Record.objects.filter(object_id=object_id, type='A')

        # Check inital content for A record
        self.assertEqual(a_record.get().content, self.a, 'Wrong content')

        # Update MX content
        vms = Query({'object_id': object_id}, ['intern_ip'])
        vms.update(intern_ip=IPv4Address(a_update))
        vms.commit(user=self.user)

        a_record = Record.objects.filter(object_id=object_id, type='A')
        self.assertEqual(a_record.get().content, a_update, 'Wrong content')

    def test_object_update_attribute_remove_for_single_attribute(self):
        """Test removing the attribute value removes existing records

        When removing the value for a mapped single attribute to any object
        of any servertype with a related record using the `records` attribute
        the necessary records must be deleted.
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name)
        record_name = record.get()['hostname']
        vm = create_object(
            'vm', records={record_name}, intern_ip=self.a, mx=self.mx)
        object_id = vm.get()['object_id']

        # Ensure record exists before
        mx_record = Record.objects.filter(
            object_id=object_id, type='MX', content=self.mx)
        self.assertTrue(mx_record.exists(), 'Missing MX record')

        # Remove record
        vms = Query({'object_id': object_id}, ['mx'])
        vms.update(mx=None)
        vms.commit(user=self.user)

        # Check record is absent now
        mx_record = Record.objects.filter(
            object_id=object_id, type='MX', content=self.mx)
        self.assertFalse(mx_record.exists(), 'Record not deleted')

    def test_object_update_attribute_add_for_multi_attribute(self):
        """Test adding a attribute value creates new record(s)

        When adding a value for a mapped multi attribute of any object of any
        servertype with a related record using the `records` attribute the
        necessary records must be created.
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name)
        record_name = record.get()['hostname']
        container = create_object(
            'container', records={record_name}, txt=self.txt)
        object_id = container.get()['object_id']
        new_txt = 'rondo_bongo=149'

        txt_record = Record.objects.filter(
            object_id=object_id, type='TXT', content=new_txt)

        # Ensure record does not exist before
        self.assertFalse(txt_record.exists(), 'Extra TXT record')

        # Add txt record
        containers = Query({'object_id': object_id}, ['txt'])
        containers.get()['txt'].add(new_txt)
        containers.commit(user=self.user)

        # Check if new TXT has been created
        txt_record = Record.objects.filter(
            object_id=object_id, type='TXT', content=new_txt)
        self.assertTrue(txt_record.exists(), 'Missing new TXT record')

    def test_object_update_attribute_remove_for_multi_attribute(self):
        """Test removing a attribute value removes record(s)

        When removing a value for a mapped multi attribute of any object of
        any servertype with a related record using the `records` attribute the
        matching records must be removed.
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name)
        record_name = record.get()['hostname']
        container = create_object(
            'container', records={record_name}, txt=self.txt)
        object_id = container.get()['object_id']
        txt_remove = 'txt_example_1=abc'

        txt_record = Record.objects.filter(
            object_id=object_id, type='TXT', content=txt_remove)

        # Ensure record exists before
        self.assertTrue(txt_record.exists(), 'Missing TXT record')

        # Remove record
        containers = Query({'object_id': object_id}, ['txt'])
        containers.update(txt=set())
        containers.commit(user=self.user)

        # Ensure record has been removed
        txt_record = Record.objects.filter(
            object_id=object_id, type='TXT', content=txt_remove)
        self.assertFalse(txt_record.exists(), 'Record not removed')

    def test_record_update_hostname_updates_records(self):
        """Test updating the record hostname updates record(s)

        When updating the hostname of a object of servertype record all records
        related to it must be updated (name).
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object(
            'record', domain=domain_name, txt=self.txt, mx=self.mx)
        record_id = record.get()['object_id']
        record_name = record.get()['hostname']
        create_object('vm', records={record_name}, intern_ip=self.a)
        current_name = record.get()['hostname']
        new_name = str(time.time())

        # Ensure records exist before: 2x TXT, 1x MX, 1x A
        records = Record.objects.filter(record_id=record_id, name=current_name)
        self.assertGreaterEqual(records.count(), 4, 'Missing records')

        # Update hostname of record
        objects = Query({'object_id': record_id}, ['hostname'])
        objects.update(hostname=new_name)
        objects.commit(user=self.user)

        # Ensure old records have been removed
        records = Record.objects.filter(record_id=record_id, name=current_name)
        self.assertEqual(records.count(), 0, 'Records not removed')

        # Ensure records have been created
        new_records = Record.objects.filter(record_id=record_id, name=new_name)
        self.assertGreaterEqual(new_records.count(), 4, 'Records not updated')

    def test_record_update_ttl_updates_records(self):
        """Test updating the TTL value updates record(s) TTL value"""

        domain_name = create_object('domain').get()['hostname']
        record = create_object(
            'record', domain=domain_name, txt=self.txt, mx=self.mx, ttl=333)
        record_name = record.get()['hostname']
        record_id = record.get()['object_id']
        create_object('vm', records={record_name}, intern_ip=self.a)

        # Check current TTL
        records = Record.objects.filter(record_id=record_id, ttl=333)
        self.assertGreater(records.count(), 0, 'Too few records found!')
        for record in records:
            self.assertEqual(record.ttl, 333, 'Wrong TTL value')

        records = Query({'hostname': record_name}, ['ttl'])
        records.update(ttl=999)
        records.commit(user=self.user)

        # Check new TTL
        records = Record.objects.filter(record_id=record_id, ttl=999)
        self.assertGreater(records.count(), 0, 'Too few records found!')
        for record in records:
            self.assertEqual(record.ttl, 999, 'Wrong TTL value')

    def test_object_remove_single_attribute_restores_record(self):
        """Test deleting an object override restores the record value

        When deleting the value from a single attribute of an object that is
        an override for a record the original value from the record must be
        restored as record.

        :return:
        """

        domain = create_object('domain')
        record = create_object(
            'record', domain=domain.get()['hostname'], mx=self.mx)
        record_id = record.get()['object_id']
        conatainer = create_object(
            'container', records={record.get()['hostname']},
            mx=self.mx_override)

        conatainer.update(mx=None)
        conatainer.commit(user=self.user)

        records = Record.objects.filter(record_id=record_id, type='MX')
        self.assertEqual(records.count(), 1, 'Wrong number of MX records')
        self.assertEqual(
            records.get().content, self.mx, 'Wrong record content')

    def test_object_remove_multi_attribute_restores_record(self):
        """Test deleting an object override restores the record value

        When deleting all values from a multi attribute of an object that is
        an override for a record the original values from the record must be
        restored as record.

        :return:
        """

        domain = create_object('domain')
        record = create_object(
            'record', domain=domain.get()['hostname'], txt=self.txt)
        record_id = record.get()['object_id']
        conatainer = create_object(
            'container', records={record.get()['hostname']},
            txt=self.txt_override)

        conatainer.update(txt={})
        conatainer.commit(user=self.user)

        records = Record.objects.filter(record_id=record_id, type='TXT')
        self.assertEqual(records.count(), 2, 'Wrong number of MX records')
        for record in records:
            self.assertIn(
                record.content, self.txt, 'Wrong record content')
