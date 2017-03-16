
from ansible.module_utils.basic import *


def main():
    module = AnsibleModule(
        argument_spec = dict(
            name=dict(required=True)
        )
    )
    name = module.params['name']
    msg = "Hello {}".format('testname')
    module.exit_json(changed=True,
                     ansible_facts=dict(
                             apigee_hello_facts=dict(
                                     custom_hello_message=msg
                             )
                     )
                     )


if __name__ == '__main__':
    main()

