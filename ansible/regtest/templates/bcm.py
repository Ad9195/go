#!/usr/bin/env python
#
#send command into broadcom shell and return result
#expect bcm_shell already running on local machine in a screen shell
#
# Usage: python bcm.py [help]
#

import sys
import re
import pexpect

#
# For talking to bcm-shell.
#
bcm_pe = None

#----------------------------------------------------
#
# bcm_wait_prompt
#
# Wait for prompt to return.
#
def bcm_wait_prompt():
    try:
        bcm_pe.expect("BCM", timeout=5)
    except:
        return(False)
    #endtry
    return(True)
#enddef

#
# bcm_conenct
#
# Setup pexpect so we have connection to the bcm-shell to send commands to
# bcm.0 (spine), bcm.2 (leaf ports ce0-ce15), and bcm.1 (leaf ports ce16-ce31).
#
def bcm_connect():
    global bcm_pe

    bcm_pe = pexpect.spawn("screen -r")
    if (bcm_pe == None): return(False)

    bcm_pe.sendline("\n")
    bcm_pe.sendline("\n")
    bcm_pe.sendline("\n")
    bcm_pe.sendline("\n")
    bcm_pe.sendline("\n")
    bcm_pe.sendline("\n")
    if (bcm_wait_prompt() == False): return(False)

    if (bcm_wait_prompt() == False): return(False)
    return(True)
#enddef

#
# bcm_disconnect
#
# Disconnect from telenet which terminates the bcm-shell.
#
def bcm_disconnect():
    global bcm_pe

    bcm_pe.sendcontrol("a")
    bcm_pe.sendline("d")
    bcm_pe = None
    #try:
    #    bcm_pe.expect("platina@ubuntu:~/bin$", timeout=5)
    #    bcm_pe = None
    #except:
    #    return(False)
    #endtry
    return(True)
#enddef

#
# bcm_send
#
# Send command to bcm-shell. If there is a multi-command in variable "command"
# make sure we put chip unit number in front of each of them. Value "chip"
# is in Platina naming convention (i.e. Lx-0, Lx-1, Sx-2).
#
def bcm_send(command):
    commands = command.split(";")

    new_commands = []
    for command in commands:
        new_commands.append(command)
    #endfor
    command = ";".join(new_commands)
    bcm_pe.sendline(command)
    print "{}".format(command)
#enddef

#
# bcm_read
#
# Read from bcm-shell display.
#
def bcm_read():
    output = ""
    #skip 2 first lines, which typically is the previous line command input
    #sometimes it catches "BCM.0" so rest of read doesn't happen
    #dump = bcm_pe.readline()
    #print "skipping.."+dump
    while (True):
        try:
            out = bcm_pe.read_nonblocking(size=40000, timeout=2)
            output += out
            #if (out.find("BCM.0") != -1): return(output)
            if (out.find("endCommand") != -1): return(output)
        except:
            return(output+'timed out')
        #endtry
    #endwhile
#endde

def flush():
    output = ""
    #skip 2 first lines, which typically is the previous line command input
    #sometimes it catches "BCM.0" so rest of read doesn't happen
    while (True):
        try:
            out = bcm_pe.read_nonblocking(size=40000, timeout=0.5)
            output += out
            if (out.find("BCM.0") != -1): return(output)
        except:
            return(output)
        #endtry
    #endwhile
#endde

#
# flush_read()
#
# clear out any left over lines in read buffer
# doesn' work, causes problem...
#
def flush_read():
    output = ""
    while (True):
        i = bcm_pe.expect ([pexpect.TIMEOUT, pexpect.EOF], timeout=2)
        if i == 0:
            if (repr(bcm_pe.before) == '\'\''):
                break
            print "before = {}".format(repr(bcm_pe.before))
            if bcm_pe.before:
                bcm_pe.expect (r'.+')
        else:
            break
    #end while
#endde

#----------------------------------------------

#print "len(sys.argv) = {}".format(len(sys.argv))
if (help in sys.argv or len(sys.argv) < 2):
    print
    print "Usage: bcm.py \"command\""
    print "where command is the entire line of command, inclosed in quoates, as you would enter into bcm_shell"
    print
    exit(1)
#endif

if (bcm_connect() == False): 
    print "Cannot connect to bcm_shell; check if screen -r gets to bcm_shell"
    exit(0)
#endif

#flush_read()
#do a read in lieu of a flush
#throwaway = flush()
#print "throwing away..."+throwaway

bcm_send(sys.argv[1])

bcm_send('echo endCommand')

output = bcm_read()
if (bcm_disconnect() == False):
    print "Did not quit out of screen correctly"
    exit(0)
#endif

lines = output.split("\n")
i = 1
for line in lines:
    #special2 = repr(line)
    #line = re.sub('\x1b.*?23d', '', line)
    #line = re.sub('\x1b.*?H', '', line)
    #line = re.sub('\x1b.*?C', '', line)
    #line = re.sub('\+', '   +', line)
    #special = repr(line)
    #print "line {}: {}".format(i, special)
    print "{}".format(line)
    i = i + 1

#end
