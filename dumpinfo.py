#!/usr/bin/env python

# pylint: disable=missing-docstring, locally-disabled, invalid-name, line-too-long, anomalous-backslash-in-string, too-many-arguments, too-many-locals, too-many-branches, too-many-statements


import sys
import getopt
from rcmdclass import Device, RcmdError


def usage():
    print 'Usage:\n\t', sys.argv[0], '-i cfgfile [options] host'
    print '''
        -i cfgfile      Config file
        host            Hostname of device to connect to (MUST exist in device DB)

        Options:
        -j              Dump in JSON format.
'''
    sys.exit(1)


def main():
    isJSON = False

    reload(sys)
    sys.setdefaultencoding('utf-8')

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'i:j')
    except getopt.GetoptError:
        usage()

    host = None

    for opt, arg in opts:
        if opt == '-i':
            cfgfile = arg
        elif opt == '-j':
            isJSON = True
        else:
            usage()

    if len(args) != 1:
        usage()
    else:
        host = args[0]

    try:
        dev = Device(cfgfile=cfgfile, host=host)
    except RcmdError as e:
        print e.value, '-', host
        sys.exit(1)

    if isJSON is True:
        print '{'
        print '    "host": "%s",' %(dev.host)
        print '    "mgmtip": "%s",' %(dev.ip)
        print '    "dtype": "%s",' %(dev.dtype)
        print '    "conn": "%s",' %(dev.conn)
        print '    "proxy": "%s",' %(dev.proxy)
        print '    "authid": "%s"' %(dev.authid)
        print '}'
    else:
        print dev.host
        print dev.ip
        print dev.dtype
        print dev.conn
        print dev.proxy
        print dev.authid


if __name__ == '__main__':
    main()
