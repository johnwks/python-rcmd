#!/usr/bin/env python3

# pylint: disable=missing-docstring, locally-disabled, invalid-name, line-too-long, anomalous-backslash-in-string, too-many-arguments, too-many-locals, too-many-branches, too-many-statements


import os
import sys
import re
import argparse
from rcmdclass import Device, RcmdError


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description='Run CLI commands on remote device.')
    parser.add_argument('host', help='Remote host to connect to.')
    parser.add_argument('-c', '--cmdfile', required=True, help='Commands file.')
    parser.add_argument('-i', '--cfgfile', required=True, help='Config file.')
    parser.add_argument('-d', '--debug', action='store_true', default=False, help='Display debugs output.')
    parser.add_argument('-a', '--osdetect', action='store_true', default=False, help='Autodetect OS.')
    parser.add_argument('-e', '--enable', action='store_true', default=False, help='Enter enable mode.')
    parser.add_argument('-n', '--smart', action='store_false', default=True, help='Disable "smart prompt" detection.')
    parser.add_argument('-l', '--log', default=None, help='Logfile to send output to.')
    parser.add_argument('-t', '--timeout', default=45, help='Timeout for commands (default 45 seconds)')
    parser.add_argument('--custom', default=None, help='''Define a custom host entry to use. The format is hostname,IP,type,method,proxy,auth
        hostname - hostname of custom host
        IP - management IP to connect to custom host
        type - device type. C=Cisco IOS, F=Cisco Firewall, N=Cisco NX-OS, E=Cisco ACE, J=Juniper, A=Arista EOS, S=Server
        method - connection method. S=SSH, T=telnet
        proxy - proxy ID to use
        auth - auth ID to use''')
    args = parser.parse_args()
    host = args.host
    cmdfile = args.cmdfile
    cfgfile = args.cfgfile
    debug = args.debug
    osdetect = args.osdetect
    enablemode = args.enable
    smartprompt = args.smart
    customhost = args.custom
    logfile = args.log
    timeout = args.timeout

    chgprompt = False

    if re.match('[#!]', host):
        print(f'Skipping - {host}')
        sys.exit(1)

    try:
        cmdf = open(cmdfile, 'r')
    except IOError:
        print(f'ERROR: Unable to open cmdfile - {host}')
        sys.exit(1)

    try:
        if customhost is not None:
            host = customhost
            dev = Device(cfgfile=cfgfile, customhost=customhost, osdetect=osdetect)
        else:
            dev = Device(cfgfile=cfgfile, host=host, osdetect=osdetect)
    except RcmdError as e:
        print(f'{e.value} - {host}')
        sys.exit(1)

    if dev.conn == 'S':
        method = 'SSH'
    elif dev.conn == 'T':
        method = 'Telnet'
    else:
        method = 'Unknown'

    print(f'!!! Connecting to {dev.host} ({dev.ip}) using {method} !!!')

    os.environ['TERM'] = 'vt100'

    try:
        dev.connect(debug, timeout, enablemode, smartprompt)
    except RcmdError as e:
        print(f'{e.value} - {dev.host}')
        sys.exit(1)

    try:
        dev.do_sendline('')
    except RcmdError as e:
        print(f'{e.value} - {dev.host}')
        sys.exit(1)

    if logfile is not None:
        try:
            fout = open(logfile, 'w')
        except IOError:
            print(f'ERROR: Error opening logfile - {host}')
            sys.exit(1)

    for cmd in cmdf:
        line = cmd.rstrip()
        # Ignore lines starting with # or ! as comments
        if re.search(r'^[^#!]', line):
            # Asterisk (*) at the beginning of the line means the next command will change the prompt
            if re.search(r'^[*]', line):
                chgprompt = True
            # @ at the beginning of the line - send with timeout while not expecting standard prompt. @,timeout,send_string,expect_string
            elif re.search(r'^@', line):
                match = re.search(r'^@,(\d+),(.+),(.+)', line)
                if match:
                    n = match.group(1)
                    try:
                        waitsec = int(n)
                    except ValueError:
                        print('ERROR: Value after @ needs to be an integer')
                        sys.exit(1)
                    send_string = match.group(2)
                    expect_string = match.group(3)
                else:
                    print('ERROR: @ should be in the format :- @,timeout,send_string,expect_string')
                    sys.exit(1)
                if debug:
                    print(f'\n>>DEBUG: waitsec - {waitsec}, send_string - {send_string}, expect_string - {expect_string}\n')
                dev.do_sendline_noexpect(send_string)
                dev.do_expect(expect_string, waitsec)
            else:
                try:
                    if chgprompt is True:
                        dev.do_sendline_setprompt(line)
                        chgprompt = False
                    else:
                        dev.do_sendline(line)
                except RcmdError as e:
                    print(f'{e.value} - {dev.host}')
                    sys.exit(1)
                header = f'\n### {line} ###\n'
                output = dev.do_getbuffer()
                if logfile is not None:
                    fout.write(header + '\n')
                    fout.write(output + '\n')
                    fout.flush()

    trailer = f'\n!!! Completed     {dev.host} {dev.ip}) !!!'
    if logfile is not None:
        fout.write(trailer + '\n')
        fout.close()
    print(trailer)

    dev.disconnect()


if __name__ == '__main__':
    main()
