#!/usr/bin/env python

# pylint: disable=missing-docstring, locally-disabled, invalid-name, line-too-long, anomalous-backslash-in-string, too-many-arguments, too-many-locals, too-many-branches, too-many-statements


import sys
import re
import getopt
from rcmdclass import Device, RcmdError


def usage():
    print 'Usage:\n\t', sys.argv[0], '-i cfgfile -m Mgmt-IP [options] host'
    print '''
        -i cfgfile      Config file
        -m Mgmt-IP      Management IP to compare
        host            Hostname of device to check management IP (MUST exist in device DB)

        Options:
        -d              Debug mode
'''
    sys.exit(1)


def main():
    logfile = None
    mgmtip = None
    debug = False

    reload(sys)
    sys.setdefaultencoding('utf-8')

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'i:m:d')
    except getopt.GetoptError:
        usage()

    host = None

    for opt, arg in opts:
        if opt == '-i':
            cfgfile = arg
        elif opt == '-m':
            mgmtip = arg
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

    if mgmtip == dev.ip:
        print '%s OK' %(host)
    else:
        print '%s mgmtip == %s, dev.ip == %s' %(host, mgmtip, dev.ip)


if __name__ == '__main__':
    main()
