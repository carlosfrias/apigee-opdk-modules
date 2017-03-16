#!/usr/bin/python

from ansible.module_utils.basic import *


class NamedObject(object):

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<{0} {1}>'.format(self.__class__.__name__, self)

    def __str__(self):
        return self.name


class Planet(NamedObject):

    def __init__(self, name=''):
        self.regions = []
        super(self.__class__, self).__init__(name)

    @property
    def hosts(self):
        hosts = []
        for region in self.regions:
            hosts += region.hosts
        return hosts

    def get_host(self, name):
        return [host for host in self.hosts if host.name == name][0]

    def get_services(self, name):
        services = []
        for region in self.regions:
            services += region.get_services(name)
        return services


class Region(NamedObject):

    def __init__(self, planet, name):
        self.planet = planet
        planet.regions.append(self)
        self.name = name
        self.number = int(name.split('-')[-1])
        self.hosts = []
        super(self.__class__, self).__init__(name)

    def get_services(self, name):
        services = []
        for host in self.hosts:
            services += host.get_services(name)
        return services


class Host(object):

    def __init__(self, region, name):
        self.region = region
        region.hosts.append(self)
        self.name = name
        self.services = []

    def get_services(self, name):
        services = []
        for service in self.services:
            if service.__class__.__name__ == name:
                services.append(service)
        return services

    def __repr__(self):
        return '<{0} {1}>'.format(self.__class__.__name__, self)

    def __str__(self):
        return self.name


class Service(object):

    def __init__(self, host):
        self.host = host
        host.services.append(self)

    @property
    def local_peers(self):
        peers = []
        for service in self.host.region.get_services(self.__class__.__name__):
            if service is not self:
                peers.append(service)
        return peers

    @property
    def global_peers(self):
        peers = []
        for service in self.host.region.planet.get_services(self.__class__.__name__):
            if service is not self:
                peers.append(service)
        return peers

    def __repr__(self):
        return '<{0} {1}>'.format(self.__class__.__name__, self)

    def __str__(self):
        return self.host.name


class Cassandra(Service):

    def __str__(self):
        return '{0}:{1},1'.format(self.host.name, self.host.region.number)


class ZooKeeper(Service):

    def __init__(self, host, observer=False):
        self.observer = observer
        super(self.__class__, self).__init__(host)

    def __str__(self):
        return self.host.name + ':observer' if self.observer else ''


class OpenLDAP(Service):

    @property
    def replicates(self):
        return bool(self.local_peers) or bool(self.global_peers)


class ManagementServer(Service): pass
class EnterpriseUI(Service): pass
class Router(Service): pass
class MessageProcessor(Service): pass
class Qpidd(Service): pass
class QpidServer(Service): pass
class PostgreSQL(Service): pass
class PostgresServer(Service): pass


profile_map = dict(
    ds = [Cassandra, ZooKeeper],
    ld = [OpenLDAP],
    ms = [OpenLDAP, ManagementServer, EnterpriseUI],
    r = [Router],
    mp = [MessageProcessor],
    rmp = [Router, MessageProcessor],
    qs = [Qpidd, QpidServer],
    ps = [PostgreSQL, PostgresServer],
    sa = [Cassandra, ZooKeeper, OpenLDAP, ManagementServer, EnterpriseUI, Router, MessageProcessor],
    sax = [Qpidd, QpidServer, PostgreSQL, PostgresServer],
    aio = [Cassandra, ZooKeeper, OpenLDAP, ManagementServer, EnterpriseUI, Router, MessageProcessor, Qpidd, QpidServer, PostgreSQL, PostgresServer]
)


def parse_topology(topology):
    parsed_topology = {}
    for entry in topology:
        region, host, profiles = entry.split()
        profiles = profiles.split(',')
        if region not in parsed_topology:
            parsed_topology[region] = []
        # This somewhat awkward structure is due to the requirement that
        # order is preserved in the host list. This matters for certain
        # service types like Cassandra, Zookeeper and management server.
        parsed_topology[region].append((host, profiles))
    return parsed_topology


def build_planet(parsed_topology):
    planet = Planet()
    for region_name in sorted(parsed_topology):
        region = Region(planet, region_name)
        for hostname, profiles in parsed_topology[region.name]:
            host = Host(region, hostname)
            for profile in profiles:
                for service in profile_map[profile]:
                    service(host)
    return planet


def get_apigee_facts(topology, my_hostname):
    facts = {}
    parsed_topology = parse_topology(topology)
    planet = build_planet(parsed_topology)

    me = planet.get_host(my_hostname)
    # Find and save the list of profiles for this host.
    for region, hosts in parsed_topology.items():
        if region == me.region.name:
            for host, profiles in hosts:
                if host == me.name:
                    facts['profiles'] = profiles

    ldap_services = planet.get_services('OpenLDAP')
    ldap_hosts = [service.host for service in ldap_services]
    ldap_replication = bool(len(ldap_services) > 1)

    if me in ldap_hosts:
        if not ldap_replication:
            facts['ldap_type'] = '1'
        else:
            facts['ldap_type'] = '2'
            try:
                facts['ldap_sid'] = ldap_hosts.index(me) + 1
            except ValueError:
                facts['ldap_sid'] = 1
            ldap_primary = ldap_services[0]
            ldap_secondary = ldap_services[1]
            # The primary LDAP service should look at the secondary LDAP service for replication. All other hosts should look at
            # the primary. In the case of more than two LDAP service, this is temporary until full mesh replication is enabled.
            if ldap_primary.host is me:
                facts['ldap_peer'] = ldap_secondary.host.name
            else:
                facts['ldap_peer'] = ldap_primary.host.name

    # Calculate the pause value for each management host to avoid race conditions.
    ms_hosts = [service.host for service in planet.get_services('ManagementServer')]
    if me in ms_hosts:
        index = ms_hosts.index(me)
        pause = index * 15
        # If not the first management server, add a buffer so the first one can populate Cassandra.
        if index > 0:
            pause += 60
        facts['ms_pause'] = pause

    # Use the first MS in this DC unless there is none. If none, use the first found.
    local_ms = me.region.get_services('ManagementServer')
    if local_ms:
        facts['msip'] = local_ms[0].host.name
    else:
        facts['msip'] = planet.get_services('ManagementServer')[0].host.name

    # This can be the same across regions since pods with identical names in different regions are actually unique.
    facts['mp_pod'] = 'gateway'

    facts['region'] = me.region.name

    # Calculate the pause value for each datastore host to avoid race conditions.
    cass_hosts = [service.host for service in planet.get_services('Cassandra')]
    if me in cass_hosts:
        facts['cass_pause'] = cass_hosts.index(me)* 15

    cass_hosts = []
    # Make sure our local region comes first.
    regions = [me.region] + [region for region in planet.regions if region != me.region]
    for region in regions:
        for cassandra in region.get_services('Cassandra'):
            cass_hosts.append('{0}:{1},1'.format(cassandra.host.name, region.number))
    facts['cass_hosts'] = ' '.join(cass_hosts)

    zk_hosts = []
    for region in planet.regions:
        # Simple observer selection algorithm: If the number of regions is greater than 1 and odd,
        # place one voter in each; if the number of regions is even, place two voters in the first
        # and one in the others.
        if len(planet.regions) == 1:
            voters = 3
        elif len(planet.regions) % 2 == 0 and region.number == 1:
            voters = 2
        else:
            voters = 1
        for zk in region.get_services('ZooKeeper'):
            if voters:
                name = zk.host.name
                voters -= 1
            else:
                name = zk.host.name + ':observer'
            zk_hosts.append(name)
    facts['zk_hosts'] = ' '.join(zk_hosts)

    zk_client_hosts = []
    for zk in me.region.get_services('ZooKeeper'):
        zk_client_hosts.append(zk.host.name)
    facts['zk_client_hosts'] = ' '.join(zk_client_hosts)

    return dict(apigee=facts)


def main():
    module = AnsibleModule(
        argument_spec = dict(
            topology = dict(required=True, type='list'),
            my_hostname = dict(required=True)
        )
    )
    try:
        #topology = module.safe_eval(module.params['topology'].decode('base64'))
        topology = module.params['topology']
        my_hostname = module.params['my_hostname']
        apigee_facts = get_apigee_facts(topology, my_hostname)
        module.exit_json(changed=False, ansible_facts=apigee_facts)
    except Exception as error:
        module.fail_json(msg=str(error))


if __name__ == '__main__':
    main()
