from ipaddress import ip_address, IPv4Address
from time import time

from serveradmin.dataset import Query
from serveradmin.powerdns.models import Record
from serveradmin.powerdns.tests.base import PowerDNSTests, create_object


class PowerDNSRecordPTRTests(PowerDNSTests):
    """PowerDNS PTR Tests"""

    def test_a_record_has_ptr_record(self):
        """Test records of type A have PTR records

        When creating records of type A we must also create a PTR record.
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name)
        record_name = record.get()['hostname']
        vm = create_object('vm', records={record_name}, intern_ip=self.a)
        object_id = vm.get()['object_id']
        ptr_value = ip_address(self.a).reverse_pointer

        ptr = Record.objects.filter(
            object_id=object_id, type='PTR', name=ptr_value,
            content=record_name)
        self.assertTrue(ptr.exists(), 'No PTR record found')

    def test_aaaa_record_has_ptr_record(self):
        """Test record of type AAAA have PTR records

        When creating record of type AAAA we must also create a PTR record.
        """

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name)
        record_name = record.get()['hostname']
        vm = create_object(
            'vm', records={record_name}, intern_ip=self.a, ipv6=self.aaaa)
        object_id = vm.get()['object_id']
        ptr_values = ip_address(self.aaaa).reverse_pointer

        ptr = Record.objects.filter(
            object_id=object_id, type='PTR', name=ptr_values,
            content=record_name)
        self.assertTrue(ptr.exists(), 'No PTR record found')

    def test_ptr_record_name_is_updated(self):
        """Test changing the A record updates the PTR record"""

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name)
        record_name = record.get()['hostname']
        vm = create_object('vm', records={record_name}, intern_ip=self.a)
        hostname = vm.get()['hostname']
        object_id = vm.get()['object_id']

        ptr_name = ip_address(self.a).reverse_pointer
        ptr = Record.objects.filter(
            object_id=object_id, type='PTR', name=ptr_name,
            content=record_name)
        self.assertTrue(ptr.exists(), 'Missing PTR record')

        vms = Query({'hostname': hostname}, ['intern_ip'])
        vms.update(intern_ip=IPv4Address('10.0.0.2'))
        vms.commit(user=self.user)

        ptr_name = ip_address('10.0.0.2').reverse_pointer
        ptr = Record.objects.filter(
            object_id=object_id, type='PTR', name=ptr_name,
            content=record_name)
        self.assertTrue(ptr.exists(), 'PTR record not updated')

    def test_ptr_record_content_is_updated(self):
        """Test changing the hostname updates the PTR record content"""

        domain_name = create_object('domain').get()['hostname']
        record = create_object('record', domain=domain_name)
        record_name = record.get()['hostname']
        vm = create_object('vm', records={record_name}, intern_ip=self.a)
        object_id = vm.get()['object_id']

        ptr_name = ip_address(self.a).reverse_pointer
        ptr = Record.objects.filter(
            object_id=object_id, type='PTR', name=ptr_name,
            content=record_name)
        self.assertTrue(ptr.exists(), 'Missing PTR record')

        new_hostname = str(time())
        records = Query({'hostname': record_name}, ['hostname'])
        records.update(hostname=new_hostname)
        records.commit(user=self.user)

        ptr = Record.objects.filter(
            object_id=object_id, type='PTR', name=ptr_name,
            content=new_hostname)
        self.assertTrue(ptr.exists(), 'PTR record not updated')
