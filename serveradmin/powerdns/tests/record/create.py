from serveradmin.powerdns.models import Record
from serveradmin.powerdns.tests.base import PowerDNSTests, create_object
from serveradmin.serverdb.query_committer import CommitError


class PowerDNSRecordCreationTests(PowerDNSTests):
    """Test PowerDNS record creation"""

    def test_object_without_records(self):
        """Creating an object without records should do nothing

        :return:
        """

        records_expected = Record.objects.all().count()

        create_object('vm', intern_ip=self.a)

        records_found = Record.objects.all().count()
        self.assertEqual(
            records_expected, records_found,
            'Number of records should not change')

    def test_object_with_record_and_without_attributes(self):
        """Test object with record without attributes has no PowerDNS records

        Creating an object with record(s) but without attributes must not
        create any PowerDNS records.

        :return:
        """

        domain = create_object('domain')
        record = create_object('record', domain=domain.get()['hostname'])
        record_name = record.get()['hostname']

        records_expected = Record.objects.all().count()

        create_object('container', records={record_name})

        records_found = Record.objects.all().count()
        self.assertEqual(
            records_expected, records_found,
            'Number of records should not change')

    def test_record_without_attribute(self):
        """Test record without attributes has no PowerDNS records

        :return:
        """

        domain = create_object('domain')
        record = create_object('record', domain=domain.get()['hostname'])
        record_id = record.get()['object_id']

        records_found = Record.objects.filter(record_id=record_id)

        self.assertEqual(
            records_found.count(), 0, 'No records should be created')

    def test_record_with_single_attribute(self):
        """Test record with a single attribute creates a PowerDNS record

        :return:
        """

        domain = create_object('domain')
        record = create_object(
            'record', domain=domain.get()['hostname'], mx=self.mx)
        record_id = record.get()['object_id']

        mx_records = Record.objects.filter(record_id=record_id, type='MX')
        self.assertEqual(mx_records.count(), 1, 'Wrong number of MX records')
        self.assertEqual(
            mx_records.get().content, self.mx, 'Wrong content for MX records')

    def test_record_with_multi_attribute(self):
        """Test record with a multi attribute creates a PowerDNS records

        :return:
        """

        domain = create_object('domain')
        record = create_object(
            'record', domain=domain.get()['hostname'], txt=self.txt)
        record_id = record.get()['object_id']

        txt_records = Record.objects.filter(record_id=record_id, type='TXT')
        self.assertEqual(txt_records.count(), 2, 'Wrong number of TXT records')
        for txt_record in txt_records:
            self.assertIn(txt_record.content, self.txt)

    def test_object_with_single_attribute(self):
        """Test object with a single attribute creates a PowerDNS record

        :return:
        """

        domain = create_object('domain')
        record = create_object('record', domain=domain.get()['hostname'])
        vm = create_object(
            'vm', records={record.get()['hostname']}, intern_ip=self.a)
        object_id = vm.get()['object_id']

        a_records = Record.objects.filter(object_id=object_id, type='A')
        self.assertEqual(a_records.count(), 1, 'Wrong number of A records')
        self.assertEqual(
            a_records.get().content, self.a, 'Wrong A record content')

    def test_object_with_multi_attribute(self):
        """Test object with a multi attribute creates PowerDNS records

        :return:
        """

        domain = create_object('domain')
        record = create_object('record', domain=domain.get()['hostname'])
        container = create_object(
            'container', records={record.get()['hostname']}, txt=self.txt)
        object_id = container.get()['object_id']

        records = Record.objects.filter(object_id=object_id, type='TXT')
        self.assertEqual(records.count(), 2, 'Wrong number of TXT records')
        for r in records:
            self.assertIn(
                r.content, self.txt, 'Wrong content for TXT record')

    def test_record_ttl(self):
        """Test custom TTL is applied to records

        :return:
        """

        domain = create_object('domain')
        record = create_object(
            'record', domain=domain.get()['hostname'], mx=self.mx, ttl=333)
        record_id = record.get()['object_id']

        records = Record.objects.filter(object_id=record_id, type='MX')
        for record in records:
            self.assertEqual(record.ttl, 333, 'TTL not applied')

    def test_object_ttl(self):
        """Test custom TTL is applied to (object) records

        :return:
        """

        domain = create_object('domain')
        record = create_object(
            'record', domain=domain.get()['hostname'], ttl=333)
        vm = create_object(
            'vm', records={record.get()['hostname']}, intern_ip=self.a,
            txt=self.txt)
        object_id = vm.get()['object_id']

        records = Record.objects.filter(object_id=object_id)
        for record in records:
            self.assertEqual(record.ttl, 333, 'TTL no applied')

    def test_object_with_single_attribute_overrides_record(self):
        """Test object attribute overrides the same record attribute

        Single attributes of an object must override records of the same
        attribute from the related record.

        :return:
        """

        domain = create_object('domain')
        record = create_object(
            'record', domain=domain.get()['hostname'], mx=self.mx)
        create_object(
            'container', records={record.get()['hostname']},
            mx=self.mx_override)

        record_id = record.get()['object_id']
        records = Record.objects.filter(record_id=record_id, type='MX')
        self.assertEqual(records.count(), 1, 'Wrong number of MX records')
        self.assertEqual(
            records.get().content, self.mx_override, 'Wrong record content')

    def test_record_with_single_attribute_override_does_nothing(self):
        """Test adding a value to a record with override must do nothing

        When adding a value to a records single attribute with an active
        override nothing must happen.

        :return:
        """

        domain = create_object('domain')
        record = create_object('record', domain=domain.get()['hostname'])
        create_object(
            'container', records={record.get()['hostname']}, mx=self.mx)

        record_id = record.get()['object_id']
        records = Record.objects.filter(record_id=record_id, type='MX')
        self.assertEqual(records.count(), 1, 'Wrong number of MX records')

        # Add value to record with active override
        record.update(mx=self.mx_override)
        record.commit(user=self.user)

        records = Record.objects.filter(record_id=record_id, type='MX')
        self.assertEqual(records.count(), 1, 'Wrong number of MX records')
        self.assertEqual(
            records.get().content, self.mx, 'Wrong record content')

    def test_object_with_multi_attribute_overrides_record(self):
        """Test object attribute overrides the same record attribute

        Multi attributes of an object must override records of the same
        attribute from the related record.

        :return:
        """

        domain = create_object('domain')
        record = create_object(
            'record', domain=domain.get()['hostname'], txt=self.txt)
        create_object(
            'container', records={record.get()['hostname']},
            txt=self.txt_override)

        record_id = record.get()['object_id']
        records = Record.objects.filter(record_id=record_id, type='TXT')
        self.assertEqual(records.count(), 2, 'Wrong number of TXT records')
        for record in records:
            self.assertIn(
                record.content, self.txt_override, 'Wrong record content')

    def test_record_with_multi_attribute_override_does_nothing(self):
        """Test adding a value to a record with override must do nothing

        When adding one or more values to a multi attribute of a record with
        an active override nothing must happen.

        :return:
        """

        domain = create_object('domain')
        record = create_object('record', domain=domain.get()['hostname'])
        create_object(
            'container', records={record.get()['hostname']}, txt=self.txt)

        record.update(txt=self.txt_override)
        record.commit(user=self.user)

        record_id = record.get()['object_id']
        records = Record.objects.filter(record_id=record_id, type='TXT')
        self.assertEqual(records.count(), 2, 'Wrong number of TXT records')
        for record in records:
            self.assertIn(record.content, self.txt, 'Wrong record content')

    def test_record_without_domain_fails(self):
        """Test creating a record without domain fails

        :return:
        """

        message = 'Validation failed. Attributes violating required: domain.'
        with self.assertRaisesMessage(CommitError, message):
            create_object('record')

    def test_record_domain_id(self):
        """Test records have the correct domain id

        :return:
        """

        domain = create_object('domain')
        record = create_object(
            'record', domain=domain.get()['hostname'], mx=self.mx)

        record_id = record.get()['object_id']
        mx_record = Record.objects.get(record_id=record_id, type='MX')
        self.assertEqual(
            mx_record.domain.id, domain.get()['object_id'], 'Wrong domain id')

    def test_object_domain_id(self):
        """Test records of objects have the correct domain id

        :returns:
        """

        domain = create_object('domain')
        record = create_object('record', domain=domain.get()['hostname'])
        container = create_object(
            'container', records={record.get()['hostname']}, mx=self.mx)

        object_id = container.get()['object_id']
        mx_record = Record.objects.get(object_id=object_id, type='MX')
        self.assertEqual(mx_record.domain.id, domain.get()['object_id'],
                         'Wrong domain id')

    def test_record_record_id(self):
        """Test records have the correct record id

        :returns:
        """

        domain = create_object('domain')
        record = create_object(
            'record', domain=domain.get()['hostname'], mx=self.mx)

        record_id = record.get()['object_id']
        mx_record = Record.objects.get(record_id=record_id, type='MX')
        self.assertEqual(
            mx_record.record_id, record.get()['object_id'], 'Wrong domain id')

    def test_object_record_id(self):
        """Test records of objects have the correct record id

        :returns:
        """

        domain = create_object('domain')
        record = create_object('record', domain=domain.get()['hostname'])
        container = create_object(
            'container', records={record.get()['hostname']}, mx=self.mx)

        object_id = container.get()['object_id']
        mx_record = Record.objects.get(object_id=object_id, type='MX')
        self.assertEqual(
            mx_record.record_id, record.get()['object_id'], 'Wrong domain id')

    def test_record_object_id(self):
        """Test records have the correct object id

        :returns:
        """

        domain = create_object('domain')
        record = create_object(
            'record', domain=domain.get()['hostname'], mx=self.mx)

        record_id = record.get()['object_id']
        mx_record = Record.objects.get(record_id=record_id, type='MX')
        self.assertEqual(
            mx_record.object_id, record.get()['object_id'], 'Wrong domain id')

    def test_object_object_id(self):
        """Test records of objects have the correct object id

        :returns:
        """

        domain = create_object('domain')
        record = create_object('record', domain=domain.get()['hostname'])
        container = create_object(
            'container', records={record.get()['hostname']}, mx=self.mx)

        object_id = container.get()['object_id']
        mx_record = Record.objects.get(object_id=object_id, type='MX')
        self.assertEqual(mx_record.object_id, container.get()['object_id'],
                         'Wrong domain id')

    def test_object_multiple_records_single_attribute(self):
        """Test object with multiple records creates multiple records

        When an object relates to more than one record a PowerDNS record must
        be created for each record.

        :return:
        """

        domain = create_object('domain')
        record_1 = create_object('record', domain=domain.get()['hostname'])
        record_2 = create_object('record', domain=domain.get()['hostname'])
        records = {record_1.get()['hostname'], record_2.get()['hostname']}
        container = create_object('container', records=records, mx=self.mx)

        object_id = container.get()['object_id']
        mx_records = Record.objects.filter(object_id=object_id, type='MX')
        self.assertEqual(mx_records.count(), 2, 'Wrong number of records')
        for mx_record in mx_records:
            self.assertEqual(
                mx_record.content, self.mx, 'Wrong record content')

    def test_object_multiple_records_multi_attribute(self):
        """Test object with multiple records creates multiple records

        When an object relates to more than one record a PowerDNS record must
        be created for each record.

        :return:
        """

        domain = create_object('domain')
        record_1 = create_object('record', domain=domain.get()['hostname'])
        record_2 = create_object('record', domain=domain.get()['hostname'])
        records = {record_1.get()['hostname'], record_2.get()['hostname']}
        container = create_object('container', records=records, txt=self.txt)

        object_id = container.get()['object_id']
        txt_records = Record.objects.filter(object_id=object_id, type='TXT')
        self.assertEqual(txt_records.count(), 4, 'Wrong number of records')
        for txt_record in txt_records:
            self.assertIn(
                txt_record.content, self.txt, 'Wrong record content')
