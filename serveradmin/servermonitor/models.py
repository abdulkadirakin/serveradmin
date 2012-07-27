import socket

from django.db import models
from django.conf import settings

PERIODS = ('hourly', 'daily', 'weekly', 'monthly', 'yearly')

class GraphValue(models.Model):
    graph_name = models.CharField(max_length=50, db_column='graphname')
    hostname = models.CharField(max_length=50)
    period = models.CharField(max_length=20, db_column='spanname')
    value = models.FloatField()

    def __unicode__(self):
        return '{0}-{1} on {2}'.format(self.graph_name, self.hostname,
                self.period)

    class Meta:
        db_table = 'graph_value'

class GraphLastUpdate(models.Model):
    graph_name = models.CharField(max_length=50, db_column='graphname')
    hostname = models.CharField(max_length=50)
    period = models.CharField(max_length=20, db_column='spanname')
    last_update = models.DateTimeField(null=True)
    
    def __unicode__(self):
        return '{0}-{1} on {2}'.format(self.graph_name, self.hostname,
                self.period)

    class Meta:
        db_table = 'graph_last_update'

class ServerData(models.Model):
    hostname = models.CharField(max_length=255, primary_key=True)
    disk_free_dom0 = models.IntegerField()
    mem_free_dom0 = models.IntegerField()
    mem_installed_dom0 = models.IntegerField(null=True)
    running_vserver = models.TextField()
    cpu_sum = models.IntegerField()
    updatetime = models.IntegerField()
    cpu_info_dom0 = models.CharField(max_length=255)
    io_hw_dom0 = models.CharField(max_length=255)
    io_hddsum_dom0 = models.CharField(max_length=255)
    xen_hwcaps_dom0 = models.CharField(max_length=255)
    xen_version_dom0 = models.CharField(max_length=255)
    last_update = models.DateTimeField(null=True)

    def __unicode__(self):
        return self.hostname

    class Meta:
        db_table = 'serverdata'


def get_available_graphs(hostname):
    # FIXME: Validate hostname!
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(settings.SERVERMONITOR_SERVER)
    s.sendall('HOSTNAME==serveradmin.admin\n')
    s.sendall('GRAPHS=={0}\nDONE\n'.format(hostname))
    fileobj = s.makefile()
    return fileobj.readline().split()

def get_graph_url(hostname, graph):
    return '{url}/graph/{hostname}/{graph}.png'.format(
            url=settings.SERVERMONITOR_URL,
            hostname=hostname,
            graph=graph)

def reload_graphs(*updates):
    """Reload many graphs. Expects tuples with hostname and graphs.

    Example::
       
       reload_graphs(('techerror.support', ['io2-hourly', 'io2-daily']),
                     ('serveradmin.admin', ['net-hourly']))
    """
    # FIXME: Validate hostname!
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(settings.SERVERMONITOR_SERVER)
        s.sendall('HOSTNAME==serveradmin.admin\n')
        for hostname, graphs in updates:
            for graph in graphs:
                graph_name, period = split_graph_name(graph)
                if not period:
                    period = ''
                s.sendall('RELOAD=={graph}##{period}##{hostname}##\n'.format(
                        graph=graph_name, period=period, hostname=hostname))
        s.sendall('DONE\n')
        fileobj = s.makefile()
        return ['SUCCESS' == line.strip() for line in fileobj.readlines()]
    except socket.error:
        return [False] * sum(len(graphs) for _host, graphs in updates) 
    

_period_extensions = tuple('-' + period for period in PERIODS)
def split_graph_name(graph):
    if graph.endswith(_period_extensions):
        graph_name, period = graph.rsplit('-', 1)
        return graph_name, period
    else:
        return graph,  None

def join_graph_name(graph, period):
    return '-'.join((graph, period)) if period else graph
