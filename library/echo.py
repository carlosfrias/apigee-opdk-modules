import ast
import json
from ansible.module_utils.basic import *

def to_json(data):
    data = ast.literal_eval(data)
    data = json.dumps(data)
    data = json.loads(data)
    return data



def main():
    module = AnsibleModule(
            argument_spec = dict(
                    value=dict(required=True),
                    echo=dict(required=True)
            )
    )
    value = module.params['value']
    value = to_json(value)

    echo = module.params['echo']

    found = value[echo]

    module.exit_json(changed=True,
                     ansible_facts=dict(
                             found=found
                        )
                     )

if __name__ == '__main__':
    main()
