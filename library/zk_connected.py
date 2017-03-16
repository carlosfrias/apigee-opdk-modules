from kazoo.client import KazooClient
from ansible.module_utils.basic import *

def test_zk_connection(zk_nodes, zk_test_path, zk_test_data):
    zk = KazooClient(zk_nodes[0])
    zk.start()
    zk.ensure_path(zk_test_path)
    zk.create(zk_test_path, zk_test_data)

    zk_connected = {}
    zk_connected[zk_nodes[0]] = dict(connected = True)


    for node in zk_nodes[1:]:
        zk_test = KazooClient(node)
        zk_test.start()
        if zk.exists(zk_test_path):
            zk_test_value = zk.get(zk_test_path, zk_test_data)
            if zk_test_data == zk_test_value[0]:
                zk_connected[node] = dict(connected = True)
            else:
                zk_connected[node] = dict( connected = False)
        else:
            zk_connected[node] = dict(connected = False)
        zk_test.stop()

    zk.stop()
    return zk_connected


def main():
    def main():
        module = AnsibleModule(argument_spec=dict(
            zk_nodes = dict(required = True, type = 'list'),
            zk_test_path = dict(required = True, type = 'str'),
            zk_test_data = dict(required = True, type = 'str')
        ))
        zk_connections = test_zk_connection(module.params['zk_nodes'], module.params['zk_test_path'], module.params['zk_test_data'])

        module.exit_json(changed = True,
                         ansible_facts = dict(
                                 apigee_zk_connection_status=zk_connections
                         ))


if __name__ == '__main__':
    main()