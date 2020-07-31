import time

from serveradmin.powerdns.models import Domain, Record
from serveradmin.powerdns.tests.base import PowerDNSTests, create_object


class PowerDNSDomainUpdateTests(PowerDNSTests):
    def test_domain_name(self):
        """Test PowerDNS domain name updates when Serveradmin hostname changes

        :return:
        """

        domain_query = create_object('domain')
        domain_id = domain_query.get()['object_id']

        new_name = str(time.time())
        domain_query.update(hostname=new_name)
        domain_query.commit(user=self.user)

        domain = Domain.objects.filter(id=domain_id, name=new_name)
        self.assertTrue(domain.exists(), 'Domain name is {}'.format(new_name))

    def test_record_names(self):
        """Test PowerDNS domain name update updates record names

        :return:
        """

        domain_query = create_object('domain')
        domain_id = domain_query.get()['object_id']

        # Tests could be too fast
        time.sleep(1)

        new_name = str(time.time())
        domain_query.update(hostname=new_name)
        domain_query.commit(user=self.user)

        records = Record.objects.filter(domain_id=domain_id, name=new_name)
        # The template has 1x SOA, 1x NS record
        self.assertEqual(records.count(), 2, 'Not all record names updated')

    def test_record_names_updates_change_date(self):
        """Test PowerDNS domain name update updates records change_date

        :return:
        """

        domain_query = create_object('domain')

        domain_id = domain_query.get()['object_id']
        change_dates = Record.objects.filter(
            domain_id=domain_id).values_list('change_date', flat=True)

        # Tests could be too fast
        time.sleep(1)

        new_name = str(time.time())
        domain_query.update(hostname=new_name)
        domain_query.commit(user=self.user)

        new_change_dates = Record.objects.filter(
            domain_id=domain_id).values_list('change_date', flat=True)

        self.assertNotEqual(
            change_dates, new_change_dates, 'Not all change dates updated')

    def test_change_soa_value(self):
        """Test changing the soa attribute updates the PowerDNS SOA record

        :return:
        """

        domain_query = create_object('domain')
        domain_id = domain_query.get()['object_id']

        new_soa = self.soa + 'abc'
        domain_query.update(soa=new_soa)
        domain_query.commit(user=self.user)

        record = Record.objects.filter(
            domain_id=domain_id, type='SOA', content=new_soa)
        self.assertTrue(
            record.exists(),
            'SOA record content should be {}'.format(new_soa))

    def test_change_soa_value_updates_change_date(self):
        """Test changing the soa value updates the PowerDNS change date

        :return:
        """

        domain_query = create_object('domain')
        domain_id = domain_query.get()['object_id']

        # The changed_date at creation
        change_date = Record.objects.get(
            domain_id=domain_id, type='SOA').change_date

        # We may be too fast to detect a change
        time.sleep(1)
        domain_query.update(soa=self.soa + 'abc')
        domain_query.commit(user=self.user)

        new_change_date = Record.objects.get(
            domain_id=domain_id, type='SOA').change_date
        self.assertNotEqual(
            change_date, new_change_date, 'change_date is the same')

    def test_add_ns_value(self):
        """Test adding a ns attribute value creates a new PowerDNS NS record

        :return:
        """

        domain_query = create_object('domain')
        domain_id = domain_query.get()['object_id']

        to_add = 'pdns3.example.com'
        domain_query.get()['ns'].add(to_add)
        domain_query.commit(user=self.user)

        record = Record.objects.filter(
            domain_id=domain_id, type='NS', content=to_add)
        self.assertTrue(
            record.exists(),
            'Missing NS record with content {}'.format(to_add))

    def test_remove_ns_value(self):
        """Test removing a ns attribute value delete the PowerDNS NS record

        :return:
        """

        domain_query = create_object('domain')
        domain_id = domain_query.get()['object_id']

        to_delete = 'pdns1.example.com'
        record = Record.objects.filter(
            domain_id=domain_id, type='NS', content=to_delete)

        self.assertTrue(record.exists(), 'Record exists before')

        domain_query.get()['ns'].remove(to_delete)
        domain_query.commit(user=self.user)

        self.assertFalse(
            record.exists(), 'Record {} has been deleted'.format(to_delete))
