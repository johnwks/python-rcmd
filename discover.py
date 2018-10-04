#!/bin/env python

# pylint: disable=missing-docstring, locally-disabled, invalid-name, line-too-long, anomalous-backslash-in-string, too-many-arguments, too-many-locals, too-many-branches, too-many-statements

import os
import sys
import re
import getopt
import signal
from rcmdclass import Device, RcmdError


def sigint_handler(signum, frame):
    print '\nQuitting script - %s %s' %(signum, frame)
    sys.exit(1)


def usage():
    print 'Usage:\n\t', sys.argv[0], '-i cfgfile [options] -h host --ip <IP_ADDR>'
    print '''
        -i cfgfile      Config file
        -h host         Hostname of device to connect to
        --ip <IP_ADDR>  Management IP of device to connect to

        Options:
        -d              Debug mode
        -p <a,b,c>      Cycle through proxies (separated by comma and no spaces) and exit on success. Default is 0.
        -a <AUTH_ID>    Use Auth ID. Default is 1
        -t timeout      Define timeout for commands (default 45 seconds)
'''
    sys.exit(1)


def main():
    debug = False
    host = None
    timeout = 45
    connmethod = 'S'
    USE_AUTH = '1'
    ip = None
    cfgfile = None
    proxylist = ['0']


    reload(sys)
    sys.setdefaultencoding('utf-8')

    signal.signal(signal.SIGINT, sigint_handler)

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'i:h:dp:a:t:', ['ip='])
    except getopt.GetoptError:
        usage()

    for opt, arg in opts:
        if opt == '-i':
            cfgfile = arg
        elif opt == '-h':
            host = arg
        elif opt == '-d':
            debug = True
        elif opt == '-p':
            proxylist = arg.split(',')
        elif opt == '-a':
            USE_AUTH = arg
        elif opt == '-t':
            timeout = int(arg)
        elif opt == '--ip':
            ip = arg
        else:
            usage()

    if cfgfile is None or host is None or ip is None:
        usage()

    os.environ['TERM'] = 'vt100'

    for proxy in proxylist:
        for connmethod in ['S', 'T']:
            customhost = '%s,%s,C,%s,%s,%s' %(host, ip, connmethod, proxy, USE_AUTH)
            try:
                dev = Device(cfgfile=cfgfile, customhost=customhost, osdetect=True)
            except RcmdError as e:
                print e.value, '-', host
                sys.exit(1)
            if debug:
                if dev.conn == 'S':
                    method = 'SSH'
                elif dev.conn == 'T':
                    method = 'Telnet'
                else:
                    method = 'Unknown'
                print '!!! Connecting to %s (%s) using %s (%s) !!!' %(dev.host, dev.ip, method, proxy)
            try:
                dev.connect(debug, timeout)
            except RcmdError as e:
                if e.value == 'ERROR: Unknown device type':
                    print '%s - %s %s (%s)' %(e.value, host, ip, proxy)
                    sys.exit(1)
                if debug:
                    print '%s - %s %s' %(e.value, host, ip)
            if dev.connected:
                break
        if dev.connected:
            break

    if not dev.connected:
        print 'ERROR: Unable to discover %s - %s' %(host, ip)
        sys.exit(1)

    devprompt = dev.prompt
    #print devprompt
    #dev.dump_hex(devprompt)
    detected_hostname = re.sub(r'\\r|\\n|\\S.*|\r|\n', '', devprompt)
    #print detected_hostname
    #dev.dump_hex(detected_hostname)
    if re.search(r'@', detected_hostname):
        aa = detected_hostname.split(r'@')
        detected_hostname = aa[1]

    dev.host = dev.host.lower()
    detected_hostname = detected_hostname.lower()
    if dev.host != detected_hostname:
        sys.stdout.write('Hostname mismatch (Provided == %s but detected == %s) - ' %(dev.host, detected_hostname))
    print '%s,%s,%s,%s,%s,%s' %(detected_hostname, dev.ip, dev.dtype, dev.conn, dev.proxy, dev.authid)

    dev.disconnect()


if __name__ == '__main__':
    main()
