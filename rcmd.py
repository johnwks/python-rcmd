#!/usr/bin/env python

# pylint: disable=missing-docstring, locally-disabled, invalid-name, line-too-long, anomalous-backslash-in-string, too-many-arguments, too-many-locals, too-many-branches, too-many-statements


import os
import sys
import re
import getopt
from rcmdclass import Device, RcmdError


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
        -t timeout      Define timeout for commands (default 45 seconds)
'''
    sys.exit(1)


def main():
    logfile = None
    timeout = 45
    debug = False
    chgprompt = False

    reload(sys)
    sys.setdefaultencoding('utf-8')

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'c:i:l:t:h:d')
    except getopt.GetoptError:
        usage()

    host = None
    customhost = None

    for opt, arg in opts:
        if opt == '-c':
            cmdfile = arg
        elif opt == '-i':
            cfgfile = arg
        elif opt == '-l':
            logfile = arg
        elif opt == '-t':
            timeout = int(arg)
        elif opt == '-h':
            customhost = arg
        elif opt == '-d':
            debug = True
        else:
            usage()

    if (customhost is None) and (len(args) != 1):
        usage()
    else:
        host = args[0]

    if re.match('[#!]', host):
        print 'Skipping - %s' %(host)
        sys.exit(1)

    try:
        cmdf = open(cmdfile, 'r')
    except IOError:
        print 'ERROR: Unable to open cmdfile - %s' %(host)
        sys.exit(1)

    try:
        if customhost is not None:
            host = customhost
            dev = Device(cfgfile=cfgfile, customhost=customhost)
        else:
            dev = Device(cfgfile=cfgfile, host=host)
    except RcmdError as e:
        print e.value, '-', host
        sys.exit(1)

    if dev.conn == 'S':
        method = 'SSH'
    elif dev.conn == 'T':
        method = 'Telnet'
    else:
        method = 'Unknown'

    print '!!! Connecting to %s (%s) using %s !!!' %(dev.host, dev.ip, method)

    os.environ['TERM'] = 'vt100'

    try:
        dev.connect(debug, timeout)
    except RcmdError as e:
        print e.value, '-', dev.host
        sys.exit(1)

    try:
        dev.do_sendline('')
    except RcmdError as e:
        print e.value, '-', dev.host
        sys.exit(1)

    if logfile is not None:
        try:
            fout = open(logfile, 'wb')
        except IOError:
            print 'ERROR: Error opening logfile - %s' %(host)
            sys.exit(1)

    for cmd in cmdf:
        line = cmd.rstrip()
        # Ignore lines starting with # or ! as comments
        if re.search('^[^#!]', line):
            # Asterisk (*) at the beginning of the line means the next command will change the prompt
            if re.search('^[*]', line):
                chgprompt = True
            else:
                try:
                    if chgprompt is True:
                        dev.do_sendline_setprompt(line)
                        chgprompt = False
                    else:
                        dev.do_sendline(line)
                except RcmdError as e:
                    print e.value, '-', dev.host
                    sys.exit(1)
                header = '\n### %s ###\n' %(line)
                output = dev.do_getbuffer()
                if logfile is not None:
                    fout.write(header + '\n')
                    fout.write(output + '\n')
                    fout.flush()

    trailer = '\n!!! Completed     %s (%s) !!!' %(dev.host, dev.ip)
    if logfile is not None:
        fout.write(trailer + '\n')
        fout.close()
    print trailer

    dev.disconnect()


if __name__ == '__main__':
    main()
