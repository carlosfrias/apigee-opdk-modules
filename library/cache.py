from ansible.module_utils.basic import *

def main():
    module = AnsibleModule(
            argument_spec=dict(
                    key=dict(required=True, type='str'),
                    value=dict(required=False, type='str')
            )
    )
    kv = {module.params['key']: module.params['value']}
    module.exit_json(
            changed=True,
            ansible_facts=kv
    )

if __name__ == '__main__':
    main()
