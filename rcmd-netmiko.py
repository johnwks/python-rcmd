#!/bin/env python

# pylint: disable=missing-docstring, locally-disabled, invalid-name, line-too-long, anomalous-backslash-in-string, too-many-arguments, too-many-locals, too-many-branches, too-many-statements


import sys
import re
import getopt
import ConfigParser
import sqlite3
import signal
import socket
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException, NetMikoAuthenticationException


def usage():
    print 'Usage:\n\t', sys.argv[0], '-c cmdfile -i cfgfile [options] host'
    print '''
        -c cmdfile      Commands file
        -i cfgfile      Config file
        host            Hostname of device to connect to (MUST exist in device DB)

        Options:
        -d              Debug mode
        -h <host,...>   Define a custom host entry to use. The format is hostname,IP,type,method,proxy,auth
                            hostname - hostname of custom host
                            IP - management IP to connect to custom host
                            type - device type. C=Cisco, F=Cisco Firewall, J=Juniper, A=Arista
                            method - connection method. S=SSH, T=telnet
                            proxy - proxy ID to use
                            auth - auth ID to use
        -l logfile      Define a logfile to send output to
'''
    sys.exit(1)


def sigint_handler(signum, frame):
    print '\nQuitting script - %s %s' %(signum, frame)
    sys.exit(1)


def do_spawn_ssh(mydtype, myhost, myip, myusername, mypassword, myenablepass, mysshconfig=None):
    device = {
        'device_type': mydtype,
        'ip': myip,
        'username': myusername,
        'password': mypassword,
        'secret': myenablepass,
        'port': 22,
        'ssh_config_file': mysshconfig,
        'verbose': False,
    }

    try:
        net_connect = ConnectHandler(**device)
    except (NetMikoAuthenticationException, NetMikoTimeoutException, socket.timeout):
        print 'ERROR: Unable to SSH to device - %s (%s)' %(myhost, myip)
        sys.exit(1)

    return net_connect


def do_spawn_telnet(myhost, myip, myusername, mypassword, myenablepass):
    device = {
        'device_type': 'cisco_ios_telnet',
        'ip': myip,
        'username': myusername,
        'password': mypassword,
        'secret': myenablepass,
        'port': 23,
        'verbose': False,
    }

    try:
        net_connect = ConnectHandler(**device)
    except (NetMikoAuthenticationException, NetMikoTimeoutException, socket.timeout):
        print 'ERROR: Unable to Telnet to device - %s (%s)' %(myhost, myip)
        sys.exit(1)

    return net_connect


def main():
    logfile = None
    sshconfig = None
    debug = False
    host = None
    customhost = False
    DELAY_FACTOR = 3

    signal.signal(signal.SIGINT, sigint_handler)

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'c:i:l:h:d')
    except getopt.GetoptError:
        usage()

    for opt, arg in opts:
        if opt == '-c':
            cmdfile = arg
        elif opt == '-i':
            cfgfile = arg
        elif opt == '-l':
            logfile = arg
        elif opt == '-h':
            customhost = True
            row = arg.split(',')
            host = row[0]
            ip = row[1]
            dtype = row[2]
            conn = row[3]
            proxy = int(row[4])
            authid = int(row[5])
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

    SQLDB = config.get('DevicesDB', 'path')
    if SQLDB is None:
        print 'ERROR: Unable to get DB file from CFG file - %s' %(host)
        sys.exit(1)

    if not customhost:
        db = sqlite3.connect(SQLDB)
        cursor = db.cursor()
        cursor.execute('''SELECT * FROM Devices WHERE Hostname = ? COLLATE NOCASE LIMIT 1''', (host,))
        row = cursor.fetchone()
        if row is None:
            print 'ERROR: Device does not exist in DB - %s' %(host)
            sys.exit(1)
        else:
            host = row[0]
            ip = row[1]
            dtype = row[2]
            conn = row[3]
            proxy = int(row[4])
            authid = int(row[5])
        db.close()

    authsection = 'Auth' + str(authid)

    try:
        include_auth = config.get(authsection, 'include_auth')
    except ConfigParser.NoOptionError:
        username = config.get(authsection, 'username')
        password = config.get(authsection, 'password')
    else:
        username = config.get(include_auth, 'username')
        password = config.get(include_auth, 'password')

    try:
        enable_password = config.get(authsection, 'enable_password')
    except ConfigParser.NoOptionError:
        enable_password = password

    if proxy != 0:
        proxysection = 'Proxy' + str(proxy)
        sshconfig = config.get(proxysection, 'sshconfig')

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
        child = do_spawn_ssh(devtype, host, ip, username, password, enable_password, sshconfig)
    elif conn == 'T':
        child = do_spawn_telnet(host, ip, username, password, enable_password)
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
    trailer = '\n!!! Completed %s (%s) !!!' %(host, ip)
    if logfile != None:
        fout.write(trailer + '\n')
        fout.close()
    print trailer


if __name__ == "__main__":
    main()
