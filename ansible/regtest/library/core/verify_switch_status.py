#!/usr/bin/python
""" Verify Links """

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
import time
from ansible.module_utils.basic import AnsibleModule
from collections import OrderedDict

DOCUMENTATION = """
---
module: verify_switch_status
author: Platina Systems
short_description: Module to verify switch status.
description:
    Module to verify switch status.
options:
    switch_name:
      description:
        - Name of the switch on which tests will be performed.
      required: False
      type: str
    before:
      description:
        - Flag to indicate if verification is before or after powercycle.
      required: False
      type: bool
      default: True
    platina_redis_channel:
      description:
        - Name of the platina redis channel.
      required: False
      type: str
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
- name: Verify services and interface status before powercycle
  verify_switch_status:
    switch_name: "{{ inventory_hostname }}"
    before: True
    hash_name: "{{ hostvars['server_emulator']['hash_name'] }}"
    log_dir_path: "{{ boot_log_dir }}"
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


def verify_goes_status(module, switch_name):
    """
    Method to verify if goes status is ok or not
    :param module: The Ansible module to fetch input parameters.
    :param switch_name: Name of the switch.
    :return: String describing if goes status is ok or not
    """
    global RESULT_STATUS
    failure_summary = ''
    state = 'before' if module.params['before'] else 'after'

    # Get the GOES status info
    goes_status = execute_commands(module, 'goes status')

    if 'not ok' in goes_status.lower():
        RESULT_STATUS = False
        failure_summary += 'On switch {} '.format(switch_name)
        failure_summary += 'goes status is not ok {} powercycle\n'.format(state)

    return failure_summary


def verify_networking_status(module, switch_name):
    """
    Method to verify if goes status is ok or not
    :param module: The Ansible module to fetch input parameters.
    :param switch_name: Name of the switch.
    :return: String describing if goes status is ok or not
    """
    global RESULT_STATUS
    failure_summary = ''
    state = 'before' if module.params['before'] else 'after'

    # Get the GOES status info
    networking_status = execute_commands(module, 'service networking status')

    if 'active' not in networking_status.lower():
        RESULT_STATUS = False
        failure_summary += 'On switch {} '.format(switch_name)
        failure_summary += 'networking service status is not ok {} powercycle\n'.format(state)

    return failure_summary


def verify_port_links(module):
    """
    Method to execute and verify port links.
    :param module: The Ansible module to fetch input parameters.
    """
    global RESULT_STATUS, HASH_DICT
    failure_summary = ''
    switch_name = module.params['switch_name']
    speed = '100g'
    media = 'copper'
    fec = 'cl91'
    state = 'before' if module.params['before'] else 'after'
    platina_redis_channel = module.params['platina_redis_channel']

    # Verify goes status before upgrade
    failure_summary += verify_goes_status(module, switch_name)

    # Verify networking service status before upgrade
    failure_summary += verify_networking_status(module, switch_name)

    for eth in range(1, 33, 2):
        # Verify interface media is set to correct value
        cmd = 'goes hget {} vnet.xeth{}.media'.format(platina_redis_channel, eth)
        out = run_cli(module, cmd)
        if media not in out:
            RESULT_STATUS = False
            failure_summary += 'On switch {} '.format(switch_name)
            failure_summary += 'interface media is not set to copper '
            failure_summary += 'for the interface xeth{} {} powercycle\n'.format(eth, state)

        # Verify speed of interfaces are set to correct value
        cmd = 'goes hget {} vnet.xeth{}.speed'.format(platina_redis_channel, eth)
        out = run_cli(module, cmd)
        if speed not in out:
            RESULT_STATUS = False
            failure_summary += 'On switch {} '.format(switch_name)
            failure_summary += 'speed of the interface '
            failure_summary += 'is not set to {} for '.format(speed)
            failure_summary += 'the interface xeth{} {} powercycle\n'.format(eth, state)

        # Verify fec of interfaces are set to correct value
        cmd = 'goes hget {} vnet.xeth{}.fec'.format(platina_redis_channel, eth)
        out = run_cli(module, cmd)
        if fec not in out:
            RESULT_STATUS = False
            failure_summary += 'On switch {} '.format(switch_name)
            failure_summary += 'fec is not set to {} for '.format(fec)
            failure_summary += 'the interface xeth{} {} powercycle\n'.format(eth, state)

        if eth%2 != 0:
            # Verify if port links are up
            cmd = 'goes hget {} vnet.xeth{}.link'.format(platina_redis_channel, eth)
            out = run_cli(module, cmd)
            if 'true' not in out:
                RESULT_STATUS = False
                failure_summary += 'On switch {} '.format(switch_name)
                failure_summary += 'port link is not up '
                failure_summary += 'for the interface xeth{} {} powercycle\n'.format(eth, state)

    # Verify cmdline status    below command are not valid for current version of redis
    #cmd = 'redis-cli -h 172.17.3.{} hget platina-mk1-bmc "cmdline.start"'.format(switch_name[-2::])
    #out = execute_commands(module, cmd)
    #if 'true' not in out:
    #    RESULT_STATUS = False
    #    failure_summary += 'On switch {} '.format(switch_name)
    #    failure_summary += 'command line is not working '
    #    failure_summary += '{} powercycle\n'.format(state)

    HASH_DICT['result.detail'] = failure_summary


def main():
    """ This section is for arguments parsing """
    module = AnsibleModule(
        argument_spec=dict(
            switch_name=dict(required=False, type='str'),
            before=dict(required=False, type='bool', default=True),
            platina_redis_channel=dict(required=False, type='str'),
            hash_name=dict(required=False, type='str'),
            log_dir_path=dict(required=False, type='str'),

        )
    )

    global HASH_DICT, RESULT_STATUS

    # Verify port link
    verify_port_links(module)

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

