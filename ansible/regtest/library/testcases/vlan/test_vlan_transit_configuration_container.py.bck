#!/usr/bin/python
""" Test Vlan Configurations """

#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible. If not, see <http://www.gnu.org/licenses/>.
#

import shlex

from collections import OrderedDict

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = """
---
module: test_vlan_configuration
author: Platina Systems
short_description: Module to verify vlan configurations.
description:
    Module to test different vlan configurations.
options:
    switch_name:
      description:
        - Name of the switch on which tests will be performed.
      required: False
      type: str
    container:
      description:
        - Name of the container.
      required: False
      type: str
    leaf_list:
      description:
        - List of all leaf switches.
      required: False
      type: list
      default: []
    spine_list:
      description:
        - List of all spine switches.
      required: False
      type: list
      default: []
    ping_switch:
      description:
        - Name of switch from which ping need to be initiated.
      required: False
      type: list
      default: []
    eth_list:
      description:
        - List of eth interfaces on leaf_switch which are connected to spines.
      required: False
      type: list
      default: []    
    config_file:
      description:
        - ospfd.conf file added in the given container.
      required: False
      type: str
    tagged:
      description:
        - Flag to indicate if to test tagged(True) packets or untagged.
      required: False
      type: bool
      default: False
    hash_name:
      description:
        - Name of the hash in which to store the result in redis.
      required: False
      type: str
    log_dir_path:
      description:
        - Path to log directory where logs will be stored.
      required: False
      type: str
"""

EXAMPLES = """
- name: Verify vlan configurations
  test_vlan_configurations:
    switch_name: "{{ inventory_hostname }}"
    ping_switch: "{{ groups['leaf'][0] }}"
    leaf_list: "{{ groups['leaf'] }}"
    eth_list: "19,3"
    hash_name: "{{ hostvars['server_emulator']['hash_name'] }}"
    log_dir_path: "{{ port_provision_log_dir }}"
"""

RETURN = """
hash_dict:
  description: Dictionary containing key value pairs to store in hash.
  returned: always
  type: dict
"""

RESULT_STATUS = True
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

    out = run_cli(module, cmd)

    # Store command prefixed with exec time as key and
    # command output as value in the hash dictionary
    exec_time = run_cli(module, 'date +%Y%m%d%T')
    key = '{0} {1} {2}'.format(module.params['switch_name'], exec_time, cmd)
    HASH_DICT[key] = out

    return out


def get_cli(module):
    """
    Method to get initial cli string.
    :param module: The Ansible module to fetch input parameters.
    :return: Initial cli/cmd string.
    """
    return "docker exec -i {} ".format(module.params['container'])


def verify_vlan_configurations(module):
    """
    Method to verify vlan configurations.
    :param module: The Ansible module to fetch input parameters.
    """
    global RESULT_STATUS, HASH_DICT
    failure_summary = ''
    switch_name = module.params['switch_name']
    leaf_list = module.params['leaf_list']
    spine_list = module.params['spine_list']
    ping_switch = module.params['ping_switch']
    eth_list = module.params['eth_list'].split(',')
    tagged = module.params['tagged']
    if module.params['config_file']:
        config_file = module.params['config_file'].splitlines()
    eth_ping_switch = []

    is_ping_switch = True if switch_name == ping_switch else False

    if is_ping_switch:
        for line in config_file:
            line = line.strip()
            if 'interface' in line:
                eth_ping_switch.append(line.split()[1])

    if tagged:
        if is_ping_switch:
            # Initiate ping for tagged packets
            for switch in leaf_list:
                if switch != ping_switch:
                    last_octet = switch[-2::]
                    for eth in eth_list:
                        cmd = get_cli(module) + "ping -c 60 192.168.{}.{}".format(eth, last_octet)
                        execute_commands(module, cmd)

        else:
            # Initiate tcpdump on target switch
            if switch_name in leaf_list:
                for eth in eth_list:
                    cmd = "timeout 70 tcpdump -c 5 -net -i xeth{} icmp".format(eth)
                    tcpdump_out = execute_commands(module, cmd)

                    if tcpdump_out:
                        if ('802.1Q (0x8100)' not in tcpdump_out or 'echo request' not in tcpdump_out or
                                'echo reply' not in tcpdump_out):
                            RESULT_STATUS = False
                            failure_summary += 'On switch {} '.format(switch_name)
                            failure_summary += 'there are no vlan tagged packets '
                            failure_summary += 'captured in tcpdump for xeth{}\n'.format(eth)
                    else:
                        RESULT_STATUS = False
                        failure_summary += 'On switch {} '.format(switch_name)
                        failure_summary += 'failed to capture tcpdump output for tagged packets\n'

            else:
                cmd = "timeout 150 tcpdump -c 1 -net -i xeth{} icmp".format(eth_list[spine_list.index(switch_name)])
                tcpdump_out = execute_commands(module, cmd)

                if tcpdump_out:
                    if '802.1Q (0x8100)' not in tcpdump_out:
                        RESULT_STATUS = False
                        failure_summary += 'On switch {} '.format(switch_name)
                        failure_summary += 'there are no vlan tagged packets '
                        failure_summary += 'captured in tcpdump for xeth{}\n'.format(eth_list[spine_list.index(switch_name)])
                else:
                    RESULT_STATUS = False
                    failure_summary += 'On switch {} '.format(switch_name)
                    failure_summary += 'failed to capture tcpdump output for tagged packets\n'

    else:
        if is_ping_switch:
            # Initiate ping for untagged packets
            for switch in leaf_list:
                if switch != ping_switch:
                    last_octet = switch[-2::]
                    for i in range(len(eth_list)):
                        cmd = "ping -c 5 -I 172.16.{}.{} 172.16.{}.{}".format(eth_ping_switch[i], ping_switch[-2::], eth_list[i], last_octet)
                        execute_commands(module, cmd)

        else:
            # Initiate tcpdump on target switch
            if switch_name in leaf_list:
                for eth in eth_list:
                    cmd = "timeout 10 tcpdump -c 5 -net -i xeth{} icmp".format(eth)
                    tcpdump_out = execute_commands(module, cmd)

                    if tcpdump_out:
                        if 'ethertype IPv4 (0x0800)' not in tcpdump_out or 'echo request' not in tcpdump_out:
                            RESULT_STATUS = False
                            failure_summary += 'On switch {} '.format(switch_name)
                            failure_summary += 'there are no vlan untagged packets '
                            failure_summary += 'captured in tcpdump for xeth{}\n'.format(eth)
                    else:
                        RESULT_STATUS = False
                        failure_summary += 'On switch {} '.format(switch_name)
                        failure_summary += 'failed to capture tcpdump output for untagged packets\n'

    HASH_DICT['result.detail'] = failure_summary

    # Get the GOES status info
    execute_commands(module, 'goes status')


def main():
    """ This section is for arguments parsing """
    module = AnsibleModule(
        argument_spec=dict(
            switch_name=dict(required=False, type='str'),
            container=dict(required=False, type='str'),
            leaf_list=dict(required=False, type='list', default=[]),
            spine_list=dict(required=False, type='list', default=[]),
            ping_switch=dict(required=False, type='str'),
            eth_list=dict(required=False, type='str'),
            tagged=dict(required=False, type='bool', default=False),
            config_file=dict(required=False, type='str'),
            hash_name=dict(required=False, type='str'),
            log_dir_path=dict(required=False, type='str'),
        )
    )

    global HASH_DICT, RESULT_STATUS

    verify_vlan_configurations(module)

    # Calculate the entire test result
    HASH_DICT['result.status'] = 'Passed' if RESULT_STATUS else 'Failed'

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

