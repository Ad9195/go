#!/usr/bin/python
""" Test/Verify Port Links """

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
module: test_port_links
author: Platina Systems
short_description: Module to execute and verify port links.
description:
    Module to execute and verify port links.
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
    is_lane2_count2:
      description:
        - Flag to indicate if lane 2 count 2 configuration is used or not.
      required: False
      type: bool
      default: False
    is_subports:
      description:
        - Flag to indicate if sub ports are used during port provisioning.
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
    platina_redis_channel:
      description:
        - Name of the platina redis channel.
      required: False
      type: str
"""

EXAMPLES = """
- name: Execute and verify port links
  test_port_links:
    switch_name: "{{ inventory_hostname }}"
    speed: "100g"
    media: "copper"
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


def verify_goes_status(module, switch_name):
    """
    Method to verify if goes status is ok or not
    :param module: The Ansible module to fetch input parameters.
    :param switch_name: Name of the switch.
    :return: String describing if goes status is ok or not
    """
    global RESULT_STATUS
    failure_summary = ''
    import time
    time.sleep(module.params['goes_delay'])
    # Get the GOES status info
    goes_status = execute_commands(module, 'goes status')

    if 'not ok' in goes_status.lower():
        RESULT_STATUS = False
        failure_summary += 'On switch {} '.format(switch_name)
        failure_summary += 'goes status is not ok\n'

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

    # Get the GOES status info
    networking_status = execute_commands(module, 'service networking status')

    if 'active' not in networking_status.lower():
        RESULT_STATUS = False
        failure_summary += 'On switch {} '.format(switch_name)
        failure_summary += 'networking service status is not ok\n'

    return failure_summary


def verify_port_links(module):
    """
    Method to execute and verify port links.
    :param module: The Ansible module to fetch input parameters.
    """
    global RESULT_STATUS, HASH_DICT
    failure_summary = ''
    switch_name = module.params['switch_name']
    speed = module.params['speed']
    media = module.params['media']
    fec = module.params['fec']
    autoneg = module.params['autoneg']
    is_subports = module.params['is_subports']
    is_lane2_count2 = module.params['is_lane2_count2']
    platina_redis_channel = module.params['platina_redis_channel']
    eth_list = ['1', '3', '5', '7', '9', '11', '13', '15', '17', '19', '21', '23', '25', '27', '29', '31']

    # Verify goes status before upgrade
    failure_summary += verify_goes_status(module, switch_name)

    # Verify networking service status before upgrade
    failure_summary += verify_networking_status(module, switch_name)

    if not is_subports:
        for ele in module.params['f_ports']:
                try:
                        eth_list.remove(str(ele))
                except:
                        pass
        for eth in eth_list:
            # Verify interface media is set to correct value
            cmd = 'goes hget {} vnet.xeth{}.media'.format(platina_redis_channel, eth)
            out = run_cli(module, cmd)
            if media not in out:
                RESULT_STATUS = False
                failure_summary += 'On switch {} '.format(switch_name)
                failure_summary += 'interface media is not set to copper '
                failure_summary += 'for the interface xeth{}\n'.format(eth)

            # Verify speed of interfaces are set to correct value
            cmd = 'goes hget {} vnet.xeth{}.speed'.format(platina_redis_channel, eth)
            out = run_cli(module, cmd)
            if speed not in out:
                RESULT_STATUS = False
                failure_summary += 'On switch {} '.format(switch_name)
                failure_summary += 'speed of the interface '
                failure_summary += 'is not set to {} for '.format(speed)
                failure_summary += 'the interface xeth{}\n'.format(eth)

            # Verify fec of interfaces are set to correct value
            cmd = 'goes hget {} vnet.xeth{}.fec'.format(platina_redis_channel, eth)
            out = run_cli(module, cmd)
            if fec not in out:
                RESULT_STATUS = False
                failure_summary += 'On switch {} '.format(switch_name)
                failure_summary += 'fec is not set to {} for '.format(fec)
                failure_summary += 'the interface xeth{}\n'.format(eth)

            # Verify if port links are up
            cmd = 'goes hget {} vnet.xeth{}.link'.format(platina_redis_channel, eth)
            out = run_cli(module, cmd)
            if 'true' not in out:
                RESULT_STATUS = False
                failure_summary += 'On switch {} '.format(switch_name)
                failure_summary += 'port link is not up '
                failure_summary += 'for the interface xeth{}\n'.format(eth)

            # Verify autoneg of interfaces are set to correct value
            cmd = 'ethtool xeth{}'.format(eth)
            out = run_cli(module, cmd)
            if 'Auto-negotiation: {}'.format(autoneg) not in out:
                RESULT_STATUS = False
                failure_summary += 'On switch {} '.format(switch_name)
                failure_summary += 'autoneg is not set to {} for '.format(autoneg)
                failure_summary += 'the interface xeth{}\n'.format(eth)

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
        for ele in module.params['f_ports']:
		try:
			eth_list.remove(str(ele))
		except:
			pass
        if not is_lane2_count2:
            subports = ['1', '2', '3', '4']
        else:
            subports = ['1', '2']
            
        for eth in eth_list:
            for port in subports:
                # Verify interface media is set to correct value
                cmd = 'goes hget {} vnet.xeth{}-{}.media'.format(platina_redis_channel, eth, port)
                out = run_cli(module, cmd)
                if media not in out:
                    RESULT_STATUS = False
                    failure_summary += 'On switch {} '.format(switch_name)
                    failure_summary += 'interface media is not set to copper '
                    failure_summary += 'for the interface xeth{}-{}\n'.format(eth, port)

                # Verify speed of interfaces are set to correct value
                cmd = 'goes hget {} vnet.xeth{}-{}.speed'.format(platina_redis_channel, eth, port)
                out = run_cli(module, cmd)
                if speed not in out:
                    RESULT_STATUS = False
                    failure_summary += 'On switch {} '.format(switch_name)
                    failure_summary += 'speed of the interface '
                    failure_summary += 'is not set to {} for '.format(speed)
                    failure_summary += 'the interface xeth{}-{}\n'.format(eth, port)

                # Verify fec of interfaces are set to correct value
                cmd = 'goes hget {} vnet.xeth{}-{}.fec'.format(platina_redis_channel, eth, port)
                out = run_cli(module, cmd)
                if fec not in out:
                    RESULT_STATUS = False
                    failure_summary += 'On switch {} '.format(switch_name)
                    failure_summary += 'fec is not set to {} for '.format(fec)
                    failure_summary += 'the interface xeth{}-{}\n'.format(eth, port)

                # Verify if port links are up
                cmd = 'goes hget {} vnet.xeth{}-{}.link'.format(platina_redis_channel, eth, port)
                out = run_cli(module, cmd)
                if 'true' not in out:
                    RESULT_STATUS = False
                    failure_summary += 'On switch {} '.format(switch_name)
                    failure_summary += 'port link is not up '
                    failure_summary += 'for the interface xeth{}-{}\n'.format(eth, port)

                # Verify autoneg of interfaces are set to correct value
                cmd = 'ethtool xeth{}-{}'.format(eth, port)
                out = run_cli(module, cmd)
                if 'Auto-negotiation: {}'.format(autoneg) not in out:
                    RESULT_STATUS = False
                    failure_summary += 'On switch {} '.format(switch_name)
                    failure_summary += 'autoneg is not set to {} for '.format(autoneg)
                    failure_summary += 'the interface xeth{}-{}\n'.format(eth, port)
        
        amedia = "fiber"
	f_ports = module.params['f_ports']
        for ele in f_ports:
		if ele % 2 == 0:
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
            media=dict(required=False, type='str'),
	    f_ports=dict(required=False, type='list', default=[]),
            fec=dict(required=False, type='str', default=''),
            autoneg=dict(required=False, type='str', default=''),
            goes_delay=dict(required=False, type='int', default=10),
	    dry_run_mode=dict(required=False, type='bool'),
            platina_redis_channel=dict(required=False, type='str'),
            is_subports=dict(required=False, type='bool', default=False),
            is_lane2_count2=dict(required=False, type='bool', default=False),
            hash_name=dict(required=False, type='str'),
            log_dir_path=dict(required=False, type='str'),
        )
    )

    global HASH_DICT, RESULT_STATUS

    # Verify port link
    if module.params['dry_run_mode']:
        cmds_list = []
	switch_name = module.params['switch_name']
    	speed = module.params['speed']
    	media = module.params['media']
    	fec = module.params['fec']
    	autoneg = module.params['autoneg']
    	is_subports = module.params['is_subports']
    	is_lane2_count2 = module.params['is_lane2_count2']
    	platina_redis_channel = module.params['platina_redis_channel']
    	eth_list = ['1', '3', '5', '7', '9', '11', '13', '15', '17', '19', '21', '23', '25', '27', '29', '31']

	execute_commands(module, 'goes status')
	execute_commands(module, 'service networking status')

	if not is_subports:
        	for eth in eth_list:
			execute_commands(module, 'goes hget {} vnet.xeth{}.media'.format(platina_redis_channel, eth))
			execute_commands(module, 'goes hget {} vnet.xeth{}.speed'.format(platina_redis_channel, eth))
			execute_commands(module, 'goes hget {} vnet.xeth{}.fec'.format(platina_redis_channel, eth))
			execute_commands(module, 'goes hget {} vnet.xeth{}.link'.format(platina_redis_channel, eth))
			execute_commands(module, 'ethtool xeth{}'.format(eth))
	else:
		for ele in module.params['f_ports']:
			try:
				eth_list.remove(ele)
			except:
				pass
		if not is_lane2_count2:
		    subports = ['1', '2', '3', '4']
		else:
		    subports = ['1', '2']

		for eth in eth_list:
            		for port in subports:
		                # Verify interface media is set to correct value
                		execute_commands(module, 'goes hget {} vnet.xeth{}-{}.media'.format(platina_redis_channel, eth, port))
				execute_commands(module, 'goes hget {} vnet.xeth{}-{}.speed'.format(platina_redis_channel, eth, port))
				execute_commands(module, 'goes hget {} vnet.xeth{}-{}.tec'.format(platina_redis_channel, eth, port))
				execute_commands(module, 'goes hget {} vnet.xeth{}-{}.link'.format(platina_redis_channel, eth, port))
				execute_commands(module, 'ethtool xeth{}-{}'.format(eth, port))
		afec = "cl91"
		amedia = "fiber"
		f_ports = module.params['f_ports']
		for ele in f_ports:
				execute_commands(module, 'goes hget {} vnet.xeth{}.fec'.format(platina_redis_channel, ele))
				execute_commands(module, 'goes hget {} vnet.xeth{}.media'.format(platina_redis_channel, ele))
				execute_commands(module, 'goes hget {} vnet.xeth{}.link'.format(platina_redis_channel, ele))
		

        for key, value in HASH_DICT.iteritems():
            cmds_list.append(key)
        # Exit the module and return the required JSON.
        module.exit_json(
            cmds=cmds_list
        )
    else:
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

