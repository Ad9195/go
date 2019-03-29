#!/usr/bin/python

""" Test/FIBER PORT CHECK """

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

import logging

logging.basicConfig(level=logging.DEBUG)

HASH_DICT = OrderedDict()

DOCUMENTATION = """
---
module: test_fiber_ports
author: Platina Systems
short_description: Module to test and verify bird configuration.
description:
    Module to test and verify bird configurations and log the same.
options:
    cmd:
	command executed for port provisioning
"""

EXAMPLES = """
- name: Verify bird peering
  test_bird_peering:
    cmd = '1,1,4,1,4,1,2,1,4,1,4,1,4,1,2,1,2,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1'
"""

RETURN = """
hash_dict:
  description: Dictionary containing key value pairs to store in hash.
  returned: always
  type: dict
"""

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

    out = run_cli(module, cmd)

    # Store command prefixed with exec time as key and
    # command output as value in the hash dictionary
    exec_time = run_cli(module, 'date +%Y%m%d%T')
    key = '{}  {}'.format(exec_time, cmd)

    return out

def interface(cmd, module):

    global HASH_DICT
    cmd1 = "goes hget platina-mk1 qsfp.compliance"
    out = execute_commands(module, cmd1).splitlines()
    eth_list1 = list()
    rcmd = cmd
    cmd = [int(i) for i in cmd]
    #print(str(cmd)+ "!@#$%")
    for line in out:
        if ("100G CWDM4" in line or "100GBASE-LR4" in line or "100GBASE-SR4" in line):
            try:
                eth_list1.append(int(line[4:6], 10))
            except:
                eth_list1.append(int(line[4:5], 10))
    eth_list = [int(i) for i in eth_list1]
    #print(str(eth_list) + "****")
    try:
    	with open("/etc/network/interfaces", "r") as fd:
        	afile = fd.readlines()
    except:
	print("File open failed")
    aoctet = afile[22].strip()[-2:]
    cnt = 0
    for eth in eth_list:
	    if eth%2 == 0:
		continue
            elif eth == 1:
		#print(eth)
                prev_line = "dns-nameservers"
            else:
		#print(str(eth) + "@")
                prev_line = "allow-vnet xeth{}\n".format(eth - 1)
            for line in enumerate(afile):
                if prev_line in line[1]:
                    aindex = line[0] + 1
                    break

            line_to_del = 12 * int(cmd[eth-1])
            cmd[eth-1] = 1
            del afile[aindex:aindex+line_to_del]
            replace = """
auto xeth{0}
iface xeth{0} inet static
    address 10.0.{0}.{1}
    netmask 255.255.255.0
pre-up ip link set $IFACE up
pre-up ethtool -s $IFACE speed 100000 autoneg off
pre-up ethtool --set-priv-flags $IFACE copper off
pre-up ethtool --set-priv-flags $IFACE fec74 off
pre-up ethtool --set-priv-flags $IFACE fec91 off
post-down ip link set $IFACE down
allow-vnet xeth{0}\n""".format(eth, aoctet) 
            afile.insert(aindex, replace)
            logging.info("aindex is {} to {}".format(aindex, line_to_del))
    with open("/etc/network/interfaces", "w") as fd:
        for line in afile:
            fd.write(line)
    astr = ""
    for ele in cmd:
	astr = astr + str(ele) + ","
  
    mod_append = 'options platina-mk1 provision='+astr[:-1]+'\n'
    fd = open("/etc/modprobe.d/goesd-platina-mk1-modprobe.conf", "r")
    mod = fd.readlines()
    mod[-1] = mod_append
    fd.close()
    with open("/etc/modprobe.d/goesd-platina-mk1-modprobe.conf", "w")as fd:
    	for line in mod:
		fd.write(line)

    HASH_DICT['command'] = astr[:-1]
    HASH_DICT['eth_list'] = eth_list


def update(cmd, module):
    global HASH_DICT
    cmd1 = "goes hget platina-mk1 qsfp.compliance"
    out = execute_commands(module, cmd1).splitlines()
    eth_list1 = list()
    speed = int(module.params['speed'])
    rcmd = cmd
    cmd = [int(i) for i in cmd]
    for line in out:
        if ("100G CWDM4" in line or "100GBASE-LR4" in line or "100GBASE-SR4" in line):
            try:
                eth_list1.append(int(line[4:6], 10))
            except:
                eth_list1.append(int(line[4:5], 10))
    eth_list = [int(i) for i in eth_list1]
    # print(str(eth_list) + "****")
    try:
        with open("/etc/network/interfaces", "r") as fd:
            afile = fd.readlines()
    except:
        print("File open failed")
    aoctet = afile[22].strip()[-2:]
    cnt = 0
    alist1 = list()
    alist2 = list()
    eth_list = [ele for ele in eth_list if ele % 2 != 0]

    for i in eth_list:
        if cmd[i - 1] != 1:
            alist1.append(i)
        else:
            alist2.append(i)

    for eth in eth_list:
        if eth == 1:
            # print(eth)
            prev_line = "dns-nameservers"
        else:
            # print(str(eth) + "@")
            prev_line = "allow-vnet xeth{}\n".format(eth - 1)
        for line in enumerate(afile):
            if prev_line in line[1]:
                aindex = line[0] + 1
                break

        line_to_del = 12 * int(cmd[eth - 1])
        del afile[aindex:aindex + line_to_del]
        if eth in alist1:
            replace = ''
            for i in range(1, cmd[eth - 1] + 1):
                replace += """
auto xeth{0}-{2}
iface xeth{0}-{2} inet static
    address 10.{0}.{2}.{1}
    netmask 255.255.255.0
pre-up ip link set $IFACE up
pre-up ethtool -s $IFACE speed {3} autoneg off
pre-up ethtool --set-priv-flags $IFACE copper off
pre-up ethtool --set-priv-flags $IFACE fec74 off
pre-up ethtool --set-priv-flags $IFACE fec91 off
post-down ip link set $IFACE down
allow-vnet xeth{0}-{2}\n""".format(eth, aoctet, i, (speed*1000))  
        else:
            replace = """
auto xeth{0}
iface xeth{0} inet static
    address 10.0.{0}.{1}
    netmask 255.255.255.0
pre-up ip link set $IFACE up
pre-up ethtool -s $IFACE speed 100000 autoneg off
pre-up ethtool --set-priv-flags $IFACE copper off
pre-up ethtool --set-priv-flags $IFACE fec74 off
pre-up ethtool --set-priv-flags $IFACE fec91 off
post-down ip link set $IFACE down
allow-vnet xeth{0}\n""".format(eth, aoctet) 
        afile.insert(aindex, replace)
        logging.info("aindex is {} to {}".format(aindex, line_to_del))
    with open("/etc/network/interfaces", "w") as fd:
        for line in afile:
            fd.write(line)

    HASH_DICT['command'] = module.params['cmd']
    HASH_DICT['eth_list'] = eth_list


def main():
    """ This section is for arguments parsing """
    module = AnsibleModule(
        argument_spec=dict(
            cmd=dict(required=False, type="str"),
            remove=dict(required=False, type="bool", default=True),
	    speed=dict(required=False, type='int', default=100),
        )
    )
    # Verify bgp neighbors
    if module.params['remove']:
        interface(module.params['cmd'].split(","), module)
    else:
        update(module.params['cmd'].split(","), module)
    module.exit_json(
            hash_dict=HASH_DICT
        )


if __name__ == '__main__':
    main()



