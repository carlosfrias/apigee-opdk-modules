from ansible.module_utils.basic import *
import yaml

def main():
    module = AnsibleModule(
            argument_spec=dict(
                    file_name=dict(required=True, type='str'),
            )
    )
    file_name = module.params['file_name']
    file = open(file_name)
    vars = yaml.load(file)
    cache = {}


    module.exit_json(
            changed=True,
            ansible_facts=cache
    )

if __name__ == '__main__':
    main()
