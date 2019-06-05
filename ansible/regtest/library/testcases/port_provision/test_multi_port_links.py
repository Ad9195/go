#!/usr/bin/python
""" Test/Verify Multi Port Links """

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
from collections import OrderedDict

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = """
---
module: test_multi_port_links
author: Platina Systems
short_description: Module to execute and verify multi port links.
description:
    Module to execute and verify port links for different speed.
options:
    switch_name:
      description:
        - Name of the switch on which tests will be performed.
      required: False
      type: str
    speed:
      description:
        - Speed of the eth interface port.
      required: False
      type: str
    media:
      description:
        - Media of the eth interface port.
      required: False
      type: str
    fec:
      description:
        - Fec of the eth interface port.
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
    platina_redis_channel:
      description:
        - Name of the platina redis channel.
      required: False
      type: str
"""

EXAMPLES = """
- name: Execute and verify port links
  test_multi_port_links:
    switch_name: "{{ inventory_hostname }}"
    speed: "100g,10g,20g,50g"
    media: "fiber"
    fec: "cl91"
    platina_redis_channel: "platina-mk1"
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

    if ('service' in cmd and 'restart' in cmd) or module.params['dry_run_mode']:
        out = None
    else:
        out = run_cli(module, cmd)


    # Store command prefixed with exec time as key and
    # command output as value in the hash dictionary
    exec_time = run_cli(module, 'date +%Y%m%d%T')
    key = '{0} {1} {2}'.format(module.params['switch_name'], exec_time, cmd)
    HASH_DICT[key] = out

    return out


def verify_port_links(module):
    """
    Method to execute and verify port links.
    :param module: The Ansible module to fetch input parameters.
    """
    global RESULT_STATUS, HASH_DICT
    failure_summary = ''
    switch_name = module.params['switch_name']
    speed_list = module.params['speed'].split(',')
    f_ports = module.params['f_ports']
    media = module.params['media']
    fec = module.params['fec']
    platina_redis_channel = module.params['platina_redis_channel']
    is_subports = False
    is_lane2_count2 = False
    eth_list = []

    for speed in speed_list:
        if speed == '100g':
            is_subports = False
	    eth_list = ['1', '17']
            fec = "cl91"
        elif speed == '10g':
            is_subports = True
            eth_list = ['3', '11', '19', '27']
            subports = ['1', '3']
            fec = "cl74"
        elif speed == '20g':
            is_subports = True
            eth_list = ['3', '11', '19', '27']
            subports = ['2', '4']
            fec = "cl74"
        elif speed == '25g':
            is_subports = True
            eth_list = ['5', '13', '21', '29']
            subports = ['1', '2', '3', '4']
            fec = "cl74"
        elif speed == '50g':
            is_subports = True
            is_lane2_count2 = True
            eth_list = ['7', '15', '23', '31']
            fec = "cl74"
        elif speed == '1g':
            is_subports = True
            eth_list = ['9', '25']
            subports = ['1', '2', '3', '4']
            speed = '1000m'
            fec = "none"

        if not is_subports:
            for ele in module.params['f_ports']:
                try:
                        eth_list.remove(str(ele))
                except:
                        pass
            for eth in eth_list:
                # Verify interface media is set to correct value
	        #time.sleep(5)
                cmd = 'goes hget {} vnet.xeth{}.media'.format(platina_redis_channel, eth)
                out = execute_commands(module, cmd)
                if media not in out:
                    RESULT_STATUS = False
                    failure_summary += 'On switch {} '.format(switch_name)
                    failure_summary += 'interface media is not set to {} '.format(media)
                    failure_summary += 'for the interface xeth{}\n'.format(eth)

                # Verify speed of interfaces are set to correct value
                cmd = 'goes hget {} vnet.xeth{}.speed'.format(platina_redis_channel, eth)
                out = execute_commands(module, cmd)
                if speed not in out:
                    RESULT_STATUS = False
                    failure_summary += 'On switch {} '.format(switch_name)
                    failure_summary += 'speed of the interface '
                    failure_summary += 'is not set to {} for '.format(speed)
                    failure_summary += 'the interface xeth{}\n'.format(eth)

                # Verify fec of interfaces are set to correct value
		#time.sleep(5)
                cmd = 'goes hget {} vnet.xeth{}.fec'.format(platina_redis_channel, eth)
                out = execute_commands(module, cmd)
                if fec not in out:
                    RESULT_STATUS = False
                    failure_summary += 'On switch {} '.format(switch_name)
                    failure_summary += 'fec is not set to {} for '.format(fec)
                    failure_summary += 'the interface xeth{}\n'.format(eth)

                # Verify if port links are up
                cmd = 'goes hget {} vnet.xeth{}.link'.format(platina_redis_channel, eth)
                out = execute_commands(module, cmd)
                if 'true' not in out:
                    RESULT_STATUS = False
                    failure_summary += 'On switch {} '.format(switch_name)
                    failure_summary += 'port link is not up '
                    failure_summary += 'for the interface xeth{}\n'.format(eth)

            amedia = "fiber"
            f_ports = module.params['f_ports']
            for ele in f_ports:
                if ele%2 == 0:
                        continue
                else:
                        cmd = "goes hget platina-mk1 qsfp.compliance"
                        out = execute_commands(module, cmd).splitlines()
                        for line in out:
                                if ("xeth{}".format(ele) in line and "100GBASE-LR4" in line):
                                        afec = "none"
                                        break
                                elif ("xeth{}".format(ele) in line and "100G CWDM4" in line):
                                        afec = "none"
                                        break
                                elif ("xeth{}".format(ele) in line and "100GBASE-SR4" in line):
                                        afec = "cl91"
                                        break
                                else:
                                        continue
                        cmd1 = 'goes hget {} vnet.xeth{}.fec'.format(platina_redis_channel, ele)
                        cmd2 = 'goes hget {} vnet.xeth{}.media'.format(platina_redis_channel, ele)
                        cmd3 = 'goes hget {} vnet.xeth{}.link'.format(platina_redis_channel, ele)
                        out1 = run_cli(module, cmd1)
                        out2 = run_cli(module, cmd2)
                        out3 = run_cli(module, cmd3)
                        if afec not in out1:
                                RESULT_STATUS = False
                                failure_summary += 'On switch {} '.format(switch_name)
                                failure_summary += 'fec of the interface {} '.format(ele)
                                failure_summary += 'is not set to {}'.format(afec)
                        if amedia not in out2:
                                RESULT_STATUS = False
                                failure_summary += 'On switch {} '.format(switch_name)
                                failure_summary += 'media of the interface {} '.format(ele)
                                failure_summary += 'is not set to {}'.format(amedia)
                        if 'true' not in out3:
                                RESULT_STATUS = False
                                failure_summary += 'On switch {} '.format(switch_name)
                                failure_summary += 'link of the interface {} '.format(ele)
                                failure_summary += 'is not set to True.\n'

        else:
            if is_lane2_count2:
                subports = ['1', '2']
            
            for ele in module.params['f_ports']:
                try:
                        eth_list.remove(str(ele))
                except:
                        pass
            for eth in eth_list:
                for port in subports:
                    # Verify interface media is set to correct value
                    cmd = 'goes hget {} vnet.xeth{}-{}.media'.format(platina_redis_channel, eth, port)
                    out = execute_commands(module, cmd)
                    if media not in out:
                        RESULT_STATUS = False
                        failure_summary += 'On switch {} '.format(switch_name)
                        failure_summary += 'interface media is not set to copper '
                        failure_summary += 'for the interface xeth{}-{}\n'.format(eth, port)

                    # Verify speed of interfaces are set to correct value
                    cmd = 'goes hget {} vnet.xeth{}-{}.speed'.format(platina_redis_channel, eth, port)
                    out = execute_commands(module, cmd)
                    if speed not in out:
                        RESULT_STATUS = False
                        failure_summary += 'On switch {} '.format(switch_name)
                        failure_summary += 'speed of the interface '
                        failure_summary += 'is not set to {} for '.format(speed)
                        failure_summary += 'the interface xeth{}-{}\n'.format(eth, port)

                    # Verify fec of interfaces are set to correct value
                    cmd = 'goes hget {} vnet.xeth{}-{}.fec'.format(platina_redis_channel, eth, port)
                    out = execute_commands(module, cmd)
                    if fec not in out:
                        RESULT_STATUS = False
                        failure_summary += 'On switch {} '.format(switch_name)
                        failure_summary += 'fec is not set to {} for '.format(fec)
                        failure_summary += 'the interface xeth{}-{}\n'.format(eth, port)

                    # Verify if port links are up
                    cmd = 'goes hget {} vnet.xeth{}-{}.link'.format(platina_redis_channel, eth, port)
                    out = execute_commands(module, cmd)
                    if 'true' not in out:
                        RESULT_STATUS = False
                        failure_summary += 'On switch {} '.format(switch_name)
                        failure_summary += 'port link is not up '
                        failure_summary += 'for the interface xeth{}-{}\n'.format(eth, port)

                amedia = "fiber"
                f_ports = module.params['f_ports']
                for ele in f_ports:
                    if ele%2 == 0:
                        continue
                    else:
                        cmd = "goes hget platina-mk1 qsfp.compliance"
                        out = execute_commands(module, cmd).splitlines()
                        for line in out:
                                if ("xeth{}".format(ele) in line and "100GBASE-LR4" in line):
                                        afec = "none"
                                        break
                                elif ("xeth{}".format(ele) in line and "100G CWDM4" in line):
                                        afec = "none"
                                        break
                                elif ("xeth{}".format(ele) in line and "100GBASE-SR4" in line):
                                        afec = "cl91"
                                        break
                                else:
                                        continue
                        cmd1 = 'goes hget {} vnet.xeth{}.fec'.format(platina_redis_channel, ele)
                        cmd2 = 'goes hget {} vnet.xeth{}.media'.format(platina_redis_channel, ele)
                        cmd3 = 'goes hget {} vnet.xeth{}.link'.format(platina_redis_channel, ele)
                        out1 = run_cli(module, cmd1)
                        out2 = run_cli(module, cmd2)
                        out3 = run_cli(module, cmd3)
                        if afec not in out1:
                                RESULT_STATUS = False
                                failure_summary += 'On switch {} '.format(switch_name)
                                failure_summary += 'fec of the interface {} '.format(ele)
                                failure_summary += 'is not set to {}'.format(afec)
                        if amedia not in out2:
                                RESULT_STATUS = False
                                failure_summary += 'On switch {} '.format(switch_name)
                                failure_summary += 'media of the interface {} '.format(ele)
                                failure_summary += 'is not set to {}'.format(amedia)
                        if 'true' not in out3:
                                RESULT_STATUS = False
                                failure_summary += 'On switch {} '.format(switch_name)
                                failure_summary += 'link of the interface {} '.format(ele)
                                failure_summary += 'is not set to True.\n'


    HASH_DICT['result.detail'] = failure_summary

    # Get the GOES status info
    execute_commands(module, 'goes status')


def main():
    """ This section is for arguments parsing """
    module = AnsibleModule(
        argument_spec=dict(
            switch_name=dict(required=False, type='str'),
            speed=dict(required=False, type='str'),
            dry_run_mode=dict(required=False, type='bool', default=False),
            media=dict(required=False, type='str'),
            fec=dict(required=False, type='str', default=''),
            platina_redis_channel=dict(required=False, type='str'),
            f_ports=dict(required=False, type='list'),
            hash_name=dict(required=False, type='str'),
            log_dir_path=dict(required=False, type='str'),
        )
    )

    global HASH_DICT, RESULT_STATUS
    if module.params['dry_run_mode']:
	cmds_list = []
        switch_name = module.params['switch_name']
    	speed_list = module.params['speed'].split(',')
    	media = module.params['media']
    	fec = module.params['fec']
    	platina_redis_channel = module.params['platina_redis_channel']
    	is_subports = False
    	is_lane2_count2 = False
    	eth_list = []

    	for speed in speed_list:
        	if speed == '100g':
            		is_subports = False
            		eth_list = ['1', '17']
            		amedia = 'fiber'
            		fec = 'cl91'
        	elif speed == '10g':
            		is_subports = True
            		eth_list = ['3', '11']
            		subports = ['1', '3']
            		fec = 'cl74'
        	elif speed == '20g':
            		is_subports = True
            		eth_list = ['3', '11']
            		subports = ['2', '4']
            		fec = 'cl74'
        	elif speed == '25g':
            		is_subports = True
            		eth_list = ['5', '13']
            		subports = ['1', '2', '3', '4']
            		fec = 'cl74'
        	elif speed == '50g':
            		is_subports = True
            		is_lane2_count2 = True
            		eth_list = ['7', '15']
            		fec = 'cl74'
        	elif speed == '1g':
            		is_subports = True
            		eth_list = ['9']
            		fec = 'none'
            		speed = '1000m'

		if not is_subports:
		    for eth in eth_list:
			# Verify interface media is set to correct value
			#time.sleep(5)
			cmd = 'goes hget {} vnet.xeth{}.media'.format(platina_redis_channel, eth)
			execute_commands(module, cmd)
			# Verify speed of interfaces are set to correct value
			cmd = 'goes hget {} vnet.xeth{}.speed'.format(platina_redis_channel, eth)
			execute_commands(module, cmd)
			# Verify fec of interfaces are set to correct value
			#time.sleep(5)
			cmd = 'goes hget {} vnet.xeth{}.fec'.format(platina_redis_channel, eth)
			execute_commands(module, cmd)
			# Verify if port links are up
			cmd = 'goes hget {} vnet.xeth{}.link'.format(platina_redis_channel, eth)
			execute_commands(module, cmd)
		else:
		    if is_lane2_count2:
			subports = ['1', '2']

		    for eth in eth_list:
			for port in subports:
			    # Verify interface media is set to correct value
			    cmd = 'goes hget {} vnet.xeth{}-{}.media'.format(platina_redis_channel, eth, port)
			    execute_commands(module, cmd)
			    # Verify speed of interfaces are set to correct value
			    cmd = 'goes hget {} vnet.xeth{}-{}.speed'.format(platina_redis_channel, eth, port)
			    execute_commands(module, cmd)
			    # Verify fec of interfaces are set to correct value
			    cmd = 'goes hget {} vnet.xeth{}-{}.fec'.format(platina_redis_channel, eth, port)
			    execute_commands(module, cmd)
			    # Verify if port links are up
			    cmd = 'goes hget {} vnet.xeth{}-{}.link'.format(platina_redis_channel, eth, port)
			    execute_commands(module, cmd)
        for key, value in HASH_DICT.iteritems():
            cmds_list.append(key)
        # Exit the module and return the required JSON.
        module.exit_json(
            cmds=cmds_list
        )


	
    else:
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


