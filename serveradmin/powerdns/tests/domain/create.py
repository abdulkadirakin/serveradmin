from serveradmin.powerdns.models import Domain, Record
from serveradmin.powerdns.tests.base import PowerDNSTests, create_object


class PowerDNSDomainCreateTests(PowerDNSTests):
    def test_domain_name(self):
        """Test PowerDNS domain has Serveradmin domain hostname as name

        :return:
        """

        name = create_object('domain').get()['hostname']
        self.assertTrue(
            Domain.objects.filter(name=name).exists(),
            'No domain with name {} found'.format(name))

    def test_domain_id(self):
        """Test PowerDNS domain has Serveradmin object_id as id

        :return:
        """

        object_id = create_object('domain').get()['object_id']
        self.assertTrue(
            Domain.objects.filter(id=object_id).exists(),
            'No domain with object_id {} found'.format(object_id))

    def test_other_servertype_creates_no_domain(self):
        """Test Serveradmin objects other than servertype domain create nothing

        :return:
        """

        object_id = create_object('container').get()['object_id']
        self.assertFalse(
            Domain.objects.filter(id=object_id).exists(),
            'Extra domain found for servertype container')

    def test_domain_type_default(self):
        """Test default PowerDNS domain type is NATIVE

        :return:
        """

        object_id = create_object('domain').get()['object_id']
        self.assertEqual(
            Domain.objects.get(id=object_id).type, 'NATIVE',
            'Default domain type must be NATIVE')

    def test_domain_type(self):
        """Test custom PowerDNS domain type equals Serveradmin object one

        :return:
        """

        object_id = create_object('domain', type='MASTER').get()['object_id']
        self.assertEqual(
            Domain.objects.get(id=object_id).type, 'MASTER',
            'Domain type must be MASTER')

    def test_domain_soa_record(self):
        """Test PowerDNS SOA record exists for a new Serveradmin domain

        :return:
        """

        object_id = create_object('domain', soa=self.soa).get()['object_id']
        record = Record.objects.filter(
            domain_id=object_id, type='SOA', content=self.soa)
        self.assertTrue(record.exists(), 'Missing SOA record')

    def test_domain_ns_records(self):
        """Test PowerDNS NS records exist for a new Serveradmin domain

        :return:
        """

        object_id = create_object('domain', ns=self.ns).get()['object_id']
        records = Record.objects.filter(
            domain_id=object_id, type='NS', content__in=self.ns)
        self.assertEqual(records.count(), 2, 'Expected 2 NS records')
