#!/bin/env python

# pylint: disable=missing-docstring, locally-disabled, invalid-name, line-too-long, anomalous-backslash-in-string, too-many-arguments, too-many-locals, too-many-branches, too-many-statements


import sys
import re
import getopt
import ConfigParser
import signal
import socket
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException, NetMikoAuthenticationException


def usage():
    print 'Usage:\n\t', sys.argv[0], '-c cmdfile -i cfgfile [options] host'
    print '''
        -c cmdfile      Commands file
        -i cfgfile      Config file
        -t device-type  Device type. J - Juniper JunOS (default), C - Cisco IOS, A - Arista EOS, F - Cisco ASA, N - Cisco NXOS
        -m conn-method  Connection method. S - SSH (default), T - telnet
        host            Hostname of device to connect to

        Options:
        -d              Debug mode
        -l logfile      Define a logfile to send output to
'''
    sys.exit(1)


def sigint_handler(signum, frame):
    print '\nQuitting script - %s %s' %(signum, frame)
    sys.exit(1)


def do_spawn_ssh(mydtype, myhost, myusername, mypassword, myenablepass):
    device = {
        'device_type': mydtype,
        'ip': myhost,
        'username': myusername,
        'password': mypassword,
        'secret': myenablepass,
        'port': 22,
        'verbose': False,
    }
    try:
        net_connect = ConnectHandler(**device)
    except (NetMikoAuthenticationException, NetMikoTimeoutException, socket.timeout):
        print 'ERROR: Unable to SSH to device - %s' %(myhost)
        sys.exit(1)
    return net_connect


def do_spawn_telnet(myhost, myusername, mypassword, myenablepass):
    device = {
        'device_type': 'cisco_ios_telnet',
        'ip': myhost,
        'username': myusername,
        'password': mypassword,
        'secret': myenablepass,
        'port': 23,
        'verbose': False,
    }
    try:
        net_connect = ConnectHandler(**device)
    except (NetMikoAuthenticationException, NetMikoTimeoutException, socket.timeout):
        print 'ERROR: Unable to Telnet to device - %s' %(myhost)
        sys.exit(1)
    return net_connect


def main():
    logfile = None
    debug = False
    host = None
    DELAY_FACTOR = 2
    dtype = 'J'
    conn = 'S'

    signal.signal(signal.SIGINT, sigint_handler)

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'c:i:l:t:m:d')
    except getopt.GetoptError:
        usage()

    for opt, arg in opts:
        if opt == '-c':
            cmdfile = arg
        elif opt == '-i':
            cfgfile = arg
        elif opt == '-l':
            logfile = arg
        elif opt == '-t':
            dtype = arg
        elif opt == '-m':
            conn = arg
        elif opt == '-d':
            debug = True
        else:
            usage()

    if host is None:
        if len(args) != 1:
            usage()
        host = args[0]

    if re.search('^[#!]', host):
        print 'Skipping - %s' %(host)
        sys.exit(1)

    try:
        cmdf = open(cmdfile, 'r')
    except IOError:
        print 'ERROR: Unable to open cmdfile - %s' %(host)
        sys.exit(1)

    try:
        cfgf = open(cfgfile, 'r')
    except IOError:
        print 'ERROR: Unable to open cfgfile - %s' %(host)
        sys.exit(1)
    cfgf.close()

    config = ConfigParser.ConfigParser()
    config.read(cfgfile)

    authsection = 'Auth'
    username = config.get(authsection, 'username')
    password = config.get(authsection, 'password')
    try:
        enable_password = config.get(authsection, 'enable_password')
    except ConfigParser.NoOptionError:
        enable_password = password

    if dtype == 'C':
        devtype = 'cisco_ios'
    elif dtype == 'J':
        devtype = 'juniper'
    elif dtype == 'A':
        devtype = 'arista_eos'
    elif dtype == 'F':
        devtype = 'cisco_asa'
    elif dtype == 'N':
        devtype = 'cisco_nxos'
    else:
        print 'ERROR: Invalid device type - %s' %(host)
        sys.exit(1)

    if conn == 'S':
        child = do_spawn_ssh(devtype, host, username, password, enable_password)
    elif conn == 'T':
        child = do_spawn_telnet(host, username, password, enable_password)
    else:
        print 'ERROR: Invalid connection type - %s' %(host)
        sys.exit(1)

    if child.check_enable_mode() is False:
        child.enable()
        if child.check_enable_mode() is False:
            print 'ERROR: Unable to enter Enable mode - %s' %(host)
            sys.exit(1)

    if logfile != None:
        try:
            fout = open(logfile, 'wb')
        except IOError:
            print 'ERROR: Error opening logfile - %s' %(host)
            sys.exit(1)

    for cmd in cmdf:
        line = cmd.rstrip()
        if re.search('^[^#!]', line):
            header = '\n### %s ###\n' %(line)
            output = child.send_command(line, delay_factor=DELAY_FACTOR)
            if logfile != None:
                fout.write(header + '\n')
                fout.write(output.encode('utf8') + '\n')
            if debug:
                print header
                print output

    child.disconnect()
    trailer = '\n!!! Completed %s !!!' %(host)
    if logfile != None:
        fout.write(trailer + '\n')
        fout.close()
    print trailer


if __name__ == "__main__":
    main()
