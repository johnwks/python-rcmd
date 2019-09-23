#!/bin/env python

# pylint: disable=missing-docstring, locally-disabled, invalid-name, line-too-long, anomalous-backslash-in-string, too-many-arguments, too-many-locals, too-many-branches, too-many-statements

import os
import sys
import re
import argparse
import signal
from rcmdclass import Device, RcmdError


def sigint_handler(signum, frame):
    print(f'\nQuitting script - {signum} {frame}')
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description='Run OS discovery on remote device.')
    parser.add_argument('-i', '--cfgfile', required=True, help='Config file.')
    parser.add_argument('--host', required=True, help='Hostname of device to connect to.')
    parser.add_argument('--ip', required=True, help='Management IP of device to connect to.')
    parser.add_argument('-d', '--debug', action='store_true', default=False, help='Display debugs output.')
    parser.add_argument('-p', '--proxy', action='append', type=int, help='Proxy to use (specify multiple times to cycle thru list).')
    parser.add_argument('-a', '--auth', default=1, type=int, help='Auth ID to use. Default is 1.')
    parser.add_argument('-t', '--timeout', default=45, type=int, help='Timeout for commands (default 45 seconds)')
    args = parser.parse_args()
    cfgfile = args.cfgfile
    host = args.host
    ip = args.ip
    debug = args.debug
    proxylist = args.proxy
    if proxylist is None:
        proxylist = [0]
    auth = args.auth
    timeout = args.timeout

    signal.signal(signal.SIGINT, sigint_handler)

    os.environ['TERM'] = 'vt100'

    for proxy in proxylist:
        for connmethod in ['S', 'T']:
            customhost = f'{host},{ip},C,{connmethod},{proxy},{auth}'
            try:
                dev = Device(cfgfile=cfgfile, customhost=customhost, osdetect=True)
            except RcmdError as e:
                print( f'{e.value} - {host}')
                sys.exit(1)
            if debug:
                if dev.conn == 'S':
                    method = 'SSH'
                elif dev.conn == 'T':
                    method = 'Telnet'
                else:
                    method = 'Unknown'
                print(f'!!! Connecting to {dev.host} ({dev.ip}) using {method} ({proxy}) !!!')
            try:
                dev.connect(debug, timeout)
            except RcmdError as e:
                if e.value == 'ERROR: Unknown device type':
                    print(f'{e.value} - {host} {ip} ({proxy})')
                    sys.exit(1)
                if debug:
                    print(f'{e.value} - {host} {ip} ({proxy})')
            if dev.connected:
                break
        if dev.connected:
            break

    if not dev.connected:
        print(f'ERROR: Unable to discover {host} - {ip}')
        sys.exit(1)

    devprompt = dev.prompt
    #print devprompt
    #dev.dump_hex(devprompt)
    detected_hostname = re.sub(r'\\r|\\n|\\S.*|\r|\n|\\', '', devprompt)
    #print detected_hostname
    #dev.dump_hex(detected_hostname)
    if re.search(r'@', detected_hostname):
        aa = detected_hostname.split(r'@')
        detected_hostname = aa[1]

    dev.host = dev.host.lower()
    detected_hostname = detected_hostname.lower()
    if dev.host != detected_hostname:
        sys.stdout.write(f'Hostname mismatch (Provided == {dev.host} but detected == {detected_hostname}) - ')
    print(f'{detected_hostname},{dev.ip},{dev.dtype},{dev.conn},{dev.proxy},{dev.authid}')

    dev.disconnect()


if __name__ == '__main__':
    main()
