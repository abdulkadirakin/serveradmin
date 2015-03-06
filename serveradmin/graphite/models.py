from string import Formatter

from django.db import models
from django.conf import settings

from serveradmin.serverdb.models import Attribute

class GraphGroup(models.Model):
    """Graph groups to be shown for the servers with defined attribute
    """

    graph_group_id = models.AutoField(primary_key=True)
    attrib = models.ForeignKey(Attribute, verbose_name='attribute')
    attrib_value = models.CharField(max_length=1024,
                                    verbose_name='attribute value')
    params = models.TextField(blank=True, help_text="""
        Part of the URL after "?" to GET the graph from the Graphite.  It
        will be concatenated with the params for the graph template and graph
        variation.  Make sure it doesn't include any character that doesn't
        allowed on URL's.  Also do not include "?" and do not put "&" at
        the end.  Example parameters:

        The params can include variables inside curly brackets like "{hostname}".
        Variables can be any string attribute except multiple ones related to
        the servers.  See Python String Formatting documentation [1] for other
        formatting options.  The dots inside the values are replaced with
        underscores in advance.

        Example params:

            width=500&height=500

        [1] https://docs.python.org/2/library/string.html#formatstrings
        """)
    sort_order = models.FloatField(default=0)
    overview = models.BooleanField(default=False, help_text="""
        Marks the graph group to be shown on the overview page.  Overview page
        isn't fully dynamic. Make sure make sure all of the graph groups
        marked as overview have the same structure.  The graphs for the group
        with the lowest sort order will be shown for every server on
        the overview page.

        For the overview page, sprites will be generated and cached on
        the server in advance to improve the loading time.  {0} will be
        appended to generated URL's to get the images for overview.
        """.format(settings.GRAPHITE_SPRITE_PARAMS))

    class Meta:
        db_table = 'graph_group'
        ordering = ('sort_order', )
        unique_together = (('attrib', 'attrib_value'), )

    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)
        self._templates = None     # To cache graph templates
        self._variations = None    # To cache graph variations

    def __unicode__(self):
        return unicode(self.attrib) + ': ' + self.attrib_value

    def get_templates(self):
        """Cache and return the graph templates
        """

        if self._templates == None:
            self._templates = list(GraphTemplate.objects.filter(graph_group=self))

        return self._templates

    def get_variations(self):
        """Cache and return the graph variations
        """

        if self._variations == None:
            self._variations = list(GraphVariation.objects.filter(graph_group=self))

        return self._variations

    def query(self, **kwargs):
        """Decorates serveradmin.dataset.query()
        """

        import serveradmin.dataset

        kwargs[self.attrib.name] = self.attrib_value

        return serveradmin.dataset.query(**kwargs)

    def graph_column(self, server, custom_params=''):
        """Generate graph URL table for a server

        Graph table is an array of tuples.  The array is ordered.  The tuples
        are used to name the elements.  Example:

            [
                ('CPU Usage', 'target=...'),
                ('Memory Usage', 'target=...'),
            ]
        """

        column = []
        for template in self.get_templates():
            formatter = AttributeFormatter()
            params = self.merged_params((template.params, custom_params))
            column.append((template.name, formatter.vformat(params, (), server)))

        return column

    def graph_table(self, server, custom_params=''):
        """Generate graph URL table for a server

        Graph table is two dimensional array of tuples.  The arrays are
        ordered.  The tuples are used to name the elements.  Example:

            [
                ('CPU Usage', [
                    ('Hourly', 'target=...'),
                    ('Daily', 'target=...'),
                    ('Weekly', 'target=...'),
                ]),
                ('Memory Usage', [
                    ('Hourly', 'target=...'),
                    ('Daily', 'target=...'),
                    ('Weekly', 'target=...'),
                ]),
            ]
        """

        table = []
        for template in self.get_templates():
            column = []
            for variation in self.get_variations():
                formatter = AttributeFormatter()
                params = self.merged_params((variation.params, template.params,
                                             custom_params))
                column.append((variation.name,
                               formatter.vformat(params, (), server)))

            table.append((template.name, column))

        return table

    def merged_params(self, other_params):
        """Get merged and cleaned URL parameters"""

        params = self.params

        for p in other_params:
            if p:
                params += '&' + p

        for r in (' ', '\t', '\n', '\r', '\v'):
            params = params.replace(r, '')

        return params

class GraphTemplate(models.Model):
    """Graph templates of the graph group
    """

    graph_group = models.ForeignKey(GraphGroup)
    name = models.CharField(max_length=64)
    params = models.TextField(blank=True, help_text="""
        Same as the params of the graph groups.
        """)
    sort_order = models.FloatField(default=0)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'graph_template'
        ordering = ('sort_order', )
        unique_together = (('graph_group', 'name'), )

    def __unicode__(self):
        return self.name

class GraphVariation(models.Model):
    """Graph variation to render the graph templates
    """

    graph_group = models.ForeignKey(GraphGroup)
    name = models.CharField(max_length=64)
    params = models.TextField(blank=True, help_text="""
        Same as the params of the graph groups.
        """)
    sort_order = models.FloatField(default=0)

    class Meta:
        db_table = 'graph_variation'
        ordering = ('sort_order', )
        unique_together = (('graph_group', 'name'), )

    def __unicode__(self):
        return self.name

class AttributeFormatter(Formatter):
    """Custom Formatter to replace variables on URL parameters

    Attributes and hostname can be used on the params supplied by the Graph
    templates and variations.  Graphite uses dots as the separator.  We chose
    to replace them with underscores.  We will apply it to all variables
    to be replaced..

    Replacing the hostname variable is easy.  Replacing variables for
    attributes requires to override the get_value() method of the base class
    which is only capable of returning the value of the given dictionary.
    To support multiple attributes, we are going to have arrays in the given
    dictionary.  Also, we would like to use all values only once to make
    a sensible use of multiple attributes.

    Furthermore, we don't want to raise an error.  We will just return
    an empty string, if the key doesn't exists.  We will cycle and use
    the same multiple attributes again, if we run out of them.
    """

    def __init__(self):
        Formatter.__init__(self)
        self._last_item_ids = {}

    def get_value(self, key, args, server):
        if key not in server:
            return ''

        if not isinstance(server[key], set):
            return self.replace_bad_characters(server, str(server[key]))

        # Initialize the last used id for the key.
        if key not in self._last_item_ids:
            self._last_item_ids[key] = 0
            return self.replace_bad_characters(server, str(server[key][0]))

        # Increment the last used id for the key.
        self._last_item_ids[key] += 1

        # Cycle the last used id for the key.
        self._last_item_ids[key] %= len(server[key])

        return self.replace_bad_characters(server, server[key][self._last_item_ids[key]])

    def replace_bad_characters(self, server, value):
        """ This method addresses the following problems:
        - dot is a separator in graphite
        - dot is part of some hostnames we have
        - minus sign, as well as dot, are not allowed in pf.conf
        So depending on type of server, those characters can be replaced with underscore.
        """

        if server['servertype'] == "loadbalancer":
            return value.replace('.', '_').replace('-', '_')
        else:
            return value.replace('.', '_')
