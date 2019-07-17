import shlex
from ansible.module_utils.basic import AnsibleModule
from collections import OrderedDict

DOCUMENTATION = """
---
module: verify_blackhole_route
author: Platina Systems
short_description: Module to verify blackhole addition to different route tables
description:
    Module to test and verify blackhole configurations and log the same.
options:
     switch_name:
      description:
        - Name of the switch on which tests will be performed.
      required: False
      type: str
    delete:
     -description: delete or add blackhole route
     type: bool
    spine_list:
      description:
        - List of all spine switches.
      required: False
      type: list
      default: []
    leaf_list:
      description:
        - List of all leaf switches.
      required: False
      type: list
      default: []
    hash_name:
      description:
        - Name of the hash in which to store the result in redis.
      required: False
      type: str
    subnet_mask:
        description:
            - subnet value for which blackhole needs to be added
    eth_list:
        description
            - list of interfaces on which blackhole will be added
    log_dir_path:
      description:
        - Path to log directory where logs will be stored.
      required: False
      type: str
"""

EXAMPLES = """
- name: Verify black hole addition to tables
  verify_blackhole_route:
          switch_name: "{{ inventory_hostname }}"
          delete: False
          eth_list: "5"
          subnet_mask: "24"
          spine_list: "{{ groups['spine'][1] }}"
          leaf_list: "{{ groups['leaf'][1] }}"
          hash_name: "{{ hostvars['server_emulator']['hash_name'] }}"
          log_dir_path: "{{ blackhole_route_dir }}"
"""

RETURN = """
hash_dict:
  description: Dictionary containing key value pairs to store in hash.
  returned: always
  type: dict
"""

HASH_DICT = OrderedDict()

def run_cli(module, cli):
    """
    Method to execute the cli command on the target node(s) and
    returns the output.
    :param module: The Ansible module to fetch input parameters.
    :param cli: The complete cli string to be executed on the target node(s).
    :return: Output/Error or None depending upon the response from cli.
    """
    cli = shlex.split(cli)
    rc, out, err = module.run_command(cli)

    if out:
        return out.rstrip()
    elif err:
        return err.rstrip()
    else:
        return None

def execute_commands(module, cmd):
    """
    Method to execute given commands and return the output.
    :param module: The Ansible module to fetch input parameters.
    :param cmd: Command to execute.
    :return: Output of the commands.
    """
    global HASH_DICT

    if ('service' in cmd and 'restart' in cmd):
        out = None
    else:
        out = run_cli(module, cmd)

    # Store command prefixed with exec time as key and
    # command output as value in the hash dictionary
    exec_time = run_cli(module, 'date +%Y%m%d%T')
    key = '{0} {1} {2}'.format(module.params['switch_name'], exec_time, cmd)
    HASH_DICT[key] = out

    return out


def add_del_blackhole(module):
    """
     Method to execute and verify port links.
     :param module: The Ansible module to fetch input parameters.
    """
    eth_list = module.params['eth_list'].split(',')
    subnet_mask = module.params['subnet_mask']
    leaf_list = module.params['leaf_list'][:]
    spine_list = module.params['spine_list'][:]
    switch_name = module.params['switch_name']
    is_subports = module.params['is_subports']
    is_lane2_count2 = module.params['is_lane2_count2']

    if is_lane2_count2:
        subports = ['1', '2']
    else:
        subports = ['1']

    blackhole_ip = []

    if switch_name in leaf_list:
        p_list = spine_list
    elif switch_name in spine_list:
        p_list = leaf_list

    if not is_subports:
        for eth in eth_list:

            if subnet_mask == "24":
                blackhole_ip.append('10.0.{}.0/24'.format(eth))
            elif subnet_mask == "32":
                blackhole_ip.append('10.0.{0}.{1}/32'.format(eth, p_list[0][-2:]))
            else:
                blackhole_ip.append('10.{}.0.0/16'.format(eth))


    else:
        if subnet_mask == '24':
            for eth in eth_list:
                for sub in subports:
                    blackhole_ip.append('10.{0}.{1}.0/24'.format(eth, sub))
        elif subnet_mask == '32':
            for eth in eth_list:
                for sub in subports:
                    blackhole_ip.append('10.{0}.{1}.{2}/32'.format(eth, sub, p_list[0][-2:]))
        else:
            for eth in eth_list:
            	blackhole_ip.append('10.{}.0.0/16'.format(eth))

    if module.params['delete']:
       execute_commands(module, 'ip route delete {}'.format(blackhole_ip[0]))
    else:
       execute_commands(module, 'ip route add blackhole {}'.format(blackhole_ip[0]))

def main():
    """ This section is for arguments parsing """
    module = AnsibleModule(
        argument_spec=dict(
            delete=dict(required=False, type='bool', default=False),
            switch_name=dict(required=False, type='str'),
            spine_list=dict(required=False, type='list', default=[]),
            leaf_list=dict(required=False, type='list', default=[]),
            subnet_mask=dict(required=False, type='str'),
            log_dir_path = dict(required=False, type='str'),
            hash_name=dict(required=False, type='str'),
            eth_list = dict(required=False, type='str', default=''),
            is_subports=dict(required=False, type='bool', default=False),
            is_lane2_count2=dict(required=False, type='bool', default=False)
        )
    )

    add_del_blackhole(module)

    # Create a log file
    log_file_path = module.params['log_dir_path']
    log_file_path += '/{}.log'.format(module.params['hash_name'])
    log_file = open(log_file_path, 'a')
    for key, value in HASH_DICT.iteritems():
        log_file.write(key)
        log_file.write('\n')
        log_file.write(str(value))
        log_file.write('\n')
        log_file.write('\n')

    log_file.close()

    # Exit the module and return the required JSON.
    module.exit_json(
        hash_dict=HASH_DICT,
        log_file_path=log_file_path
    )


if __name__ == '__main__':
    main()
