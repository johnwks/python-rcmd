#!/usr/bin/env python

# pylint: disable=missing-docstring, locally-disabled, invalid-name, line-too-long, anomalous-backslash-in-string, too-many-arguments, too-many-locals, too-many-branches, too-many-statements


import sys
import re
import getopt
from rcmdclass import Device, RcmdError


def usage():
    print 'Usage:\n\t', sys.argv[0], '-i cfgfile [options] host'
    print '''
        -i cfgfile      Config file
        host            Hostname of device to connect to (MUST exist in device DB)

        Options:
        -d              Debug mode
        -t timeout      Define timeout for commands (default 45 seconds)
'''
    sys.exit(1)


def main():
    timeout = 45
    debug = False

    reload(sys)
    sys.setdefaultencoding('utf-8')

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'i:t:d')
    except getopt.GetoptError:
        usage()

    host = None

    for opt, arg in opts:
        if opt == '-i':
            cfgfile = arg
        elif opt == '-t':
            timeout = int(arg)
        elif opt == '-d':
            debug = True
        else:
            usage()

    if len(args) != 1:
        usage()
    else:
        host = args[0]

    if re.search('^[#!]', host):
        print 'Skipping - %s' %(host)
        sys.exit(1)

    try:
        dev = Device(cfgfile=cfgfile, host=host)
    except RcmdError as e:
        print e.value, '-', host
        sys.exit(1)

    try:
        dev.connect(debug, timeout)
    except RcmdError as e:
        print e.value, '-', dev.host
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

    dev.host = dev.host.upper()
    detected_hostname = detected_hostname.upper()
    if dev.host != detected_hostname:
        print '%s - Hostname mismatch (DB == %s but detected == %s)' %(dev.host, dev.host, detected_hostname)
    else:
        print '%s - OK' %(host)

    dev.disconnect()


if __name__ == '__main__':
    main()
