#!/usr/bin/env python3

# pylint: disable=missing-docstring, locally-disabled, invalid-name, line-too-long, anomalous-backslash-in-string, too-many-arguments, too-many-locals, too-many-branches, too-many-statements


import sys
import argparse
from rcmdclass import Device, RcmdError
import pexpect


SCP = '/usr/bin/scp'


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description='scp file to remote device.')
    parser.add_argument('host', help='Remote host to connect to.')
    parser.add_argument('-i', '--cfgfile', required=True, help='Config file.')
    parser.add_argument('-f', '--file', required=True, help='File to scp.')
    parser.add_argument('-r', '--remotedir', default='', help='Remote directory to scp to.')
    parser.add_argument('-d', '--debug', action='store_true', default=False, help='Display debugs output.')
    parser.add_argument('-t', '--timeout', default=45, help='Timeout for commands (default 45 seconds)')
    parser.add_argument('-p', '--pki', action='store_true', default=False, help='Use PKI for authentication (SSH only).')
    args = parser.parse_args()
    host = args.host
    cfgfile = args.cfgfile
    file = args.file
    remotedir = args.remotedir
    debug = args.debug
    timeout = int(args.timeout)
    pki = args.pki

    try:
        dev = Device(cfgfile=cfgfile, host=host)
    except RcmdError as e:
        print(f'{e.value} - {host}')
        sys.exit(1)

    try:
        ff = open(file, 'r')
    except IOError:
        print(f'ERROR: Unable to open file - {file}')
        sys.exit(1)
    ff.close()

    cmdline = f'{SCP} {file} {dev.username}@{dev.ip}:{remotedir}'
    print(f'Executing command on {host} {dev.ip} - {cmdline}')
    try:
        child = pexpect.spawn(cmdline)
        child.expect('assword:')
        child.sendline(dev.password)
        child.wait()
        print('Done')
    except (pexpect.EOF, pexpect.TIMEOUT) as e:
        print(f'{e.value} - {host}')
        sys.exit(1)


if __name__ == '__main__':
    main()
