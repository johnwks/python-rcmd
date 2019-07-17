#!/bin/env python3

# pylint: disable=missing-docstring, locally-disabled, invalid-name, line-too-long, anomalous-backslash-in-string, too-many-arguments, too-many-locals, too-many-branches, too-many-statements

import sys
import time
import re
import configparser
import sqlite3
import pexpect


SSH = '/usr/bin/ssh'
TELNET = '/usr/bin/telnet'
SOCAT = '/usr/bin/socat'
BASE_PROMPT = r'[\r\n]([\w\d\-\+\@\/\.\(\)\~\:\/\ \[\]]+[#>%\$]|[#>%\$])'
HOST_PROMPT = r'(.*)[#>%\$]'
PROMPT_CHAR = r'[#>%\$]'
PASSWORD_PROMPT = '[Pp]assword:'
MAXREAD = 4000 * 1024
LOGINTIMEOUT = 30
MORE_PROMPTS = r'[Mm]ore( \d+\%\)---|\)---|--| --->)'


class RcmdError(Exception):

    def __init__(self, value):
        self.value = value


class Device(object):

    def __init__(self, cfgfile=None, host=None, hostregex=None, customhost=None, osdetect=False):
        self.cfgfile = cfgfile
        self.host = host
        if hostregex is not None:
            self.hostregex = hostregex.split(' ')
        else:
            self.hostregex = None
        self.ip = None
        self.dtype = None
        self.conn = None
        self.proxy = None
        self.authid = None
        self.username = None
        self.password = None
        self.enable_password = None
        self.proxysection = None
        self.pserver = None
        self.pport = None
        self.sshconfig = None
        self.valid = False
        self.connected = False
        self.debug = False
        self.child = None
        self.timeout = 45
        self.buffer = None
        self.prompt = BASE_PROMPT
        self.osdetect = osdetect
        self.enablemode = False
        self.pki = False
        HostList = []
        HostDict = {}

        if (self.host is None) and (self.hostregex is None) and (customhost is None):
            raise RcmdError('ERROR: No host or hostregex or customhost specified')

        if self.cfgfile is None:
            raise RcmdError('ERROR: No cfgfile specified')

        try:
            cfgf = open(self.cfgfile, 'r')
        except IOError:
            raise RcmdError('ERROR: Unable to open cfgfile')
        cfgf.close()

        config = configparser.ConfigParser()
        config.read(self.cfgfile)

        if customhost is not None:
            row = customhost.split(',')
            self.host = row[0]
            self.ip = row[1]
            self.dtype = row[2]
            self.conn = row[3]
            self.proxy = int(row[4])
            self.authid = int(row[5])
        else:
            SQLDB = config.get('DevicesDB', 'path')
            if SQLDB is None:
                raise RcmdError('ERROR: Unable to get DB file from CFG file')

            if host is not None:
                db = sqlite3.connect(SQLDB)
                cursor = db.cursor()
                cursor.execute('''SELECT * FROM Devices WHERE Hostname = ? COLLATE NOCASE LIMIT 1''', (host,))
                row = cursor.fetchone()
                if row is None:
                    raise RcmdError('ERROR: Device does not exist in DB')
                else:
                    self.host = row[0]
                    self.ip = row[1]
                    self.dtype = row[2]
                    self.conn = row[3]
                    self.proxy = int(row[4])
                    self.authid = int(row[5])
            else:
                hostregexsql = f'Hostname NOT NULL'
                for i in self.hostregex:
                    hostregexsql += f' AND Hostname LIKE "%{i}%"'

                db = sqlite3.connect(SQLDB)
                cursor = db.cursor()
                sqlquery = f'SELECT * FROM Devices WHERE {hostregexsql} ORDER BY Hostname ASC'
                cursor.execute(sqlquery)
                rows = cursor.fetchall()
                if not rows:
                    raise RcmdError('ERROR: Device does not exist in DB')
                elif len(rows) == 1:
                    self.host = rows[0][0]
                    self.ip = rows[0][1]
                    self.dtype = rows[0][2]
                    self.conn = rows[0][3]
                    self.proxy = int(rows[0][4])
                    self.authid = int(rows[0][5])
                else:
                    idx = 1
                    for row in rows:
                        host = row[0]
                        ip = row[1]
                        dtype = row[2]
                        conn = row[3]
                        proxy = int(row[4])
                        authid = int(row[5])
                        HostDict['index'] = idx
                        HostDict['host'] = host
                        HostDict['ip'] = ip
                        HostDict['dtype'] = dtype
                        HostDict['conn'] = conn
                        HostDict['proxy'] = proxy
                        HostDict['authid'] = authid
                        HostList.append(HostDict.copy())
                        if conn == 'S':
                            cmethod = 'SSH'
                        elif conn == 'T':
                            cmethod = 'Telnet'
                        else:
                            cmethod = 'Unknown'
                        print(f'{str(idx).rjust(4)}) {host.ljust(28)} {ip.ljust(16)} {cmethod}')
                        idx += 1
                    inidx = input('Enter selection (default is 1, q to quit): ')
                    isvalid = False
                    if inidx == 'q':
                        raise RcmdError('Quitting')
                    else:
                        if inidx == '':
                            inidx = '1'
                        try:
                            inidx = int(inidx)
                        except ValueError:
                            raise RcmdError('ERROR: Invalid selection')
                        if (inidx >= idx) or (inidx < 1):
                            raise RcmdError('ERROR: Invalid selection')
                        for j in HostList:
                            if int(j['index']) == int(inidx):
                                isvalid = True
                                self.host = j['host']
                                self.ip = j['ip']
                                self.dtype = j['dtype']
                                self.conn = j['conn']
                                self.proxy = j['proxy']
                                self.authid = j['authid']
                        if isvalid is False:
                            raise RcmdError('ERROR: Invalid selection')

            db.close()

        authsection = 'Auth' + str(self.authid)

        try:
            include_auth = config.get(authsection, 'include_auth')
        except configparser.NoOptionError:
            self.username = config.get(authsection, 'username')
            self.password = config.get(authsection, 'password')
        else:
            self.username = config.get(include_auth, 'username')
            self.password = config.get(include_auth, 'password')

        try:
            self.enable_password = config.get(authsection, 'enable_password')
        except configparser.NoOptionError:
            self.enable_password = self.password

        if self.proxy != 0:
            self.proxysection = 'Proxy' + str(self.proxy)
            self.pserver = config.get(self.proxysection, 'server')
            self.pport = config.get(self.proxysection, 'port')
            self.sshconfig = config.get(self.proxysection, 'sshconfig')

        self.valid = True

        return None


    def connect(self, debug=False, timeout=45, enablemode=False, smartprompt=True, pki=False):
        self.debug = debug
        self.timeout = timeout
        self.pki = pki

        if self.conn == 'S':
            self.do_spawn_ssh()
        elif self.conn == 'T':
            self.do_spawn_telnet()
        else:
            raise RcmdError('ERROR: Invalid connection type')

        if enablemode or self.dtype == 'F':
            self.child.sendline('enable')
            myexp = self.child.expect([PASSWORD_PROMPT, HOST_PROMPT, pexpect.EOF, pexpect.TIMEOUT], timeout=LOGINTIMEOUT)
            if myexp == 0:
                self.do_sendline(self.enable_password)
            elif myexp == 1:
                pass
            elif myexp == 2:
                raise RcmdError('ERROR: EOF encountered')
            elif myexp == 3:
                raise RcmdError('ERROR: Timeout encountered')
            else:
                raise RcmdError('ERROR: Unknown expect error')
            self.buffer = self.child.before

        if smartprompt:
            self.do_set_prompt()

        if self.osdetect:
            self.os_detect()
        else:
            if self.dtype == 'J':
                self.init_device_junos()
            elif self.dtype == 'A':
                self.init_device_eos()
            elif self.dtype == 'C':
                self.init_device_ios()
            elif self.dtype == 'N':
                self.init_device_nxos()
            elif self.dtype == 'E':
                self.init_device_ace()
            elif self.dtype == 'F':
                self.init_device_asa()
            elif self.dtype == 'L':
                self.init_device_linux()
            elif self.dtype == 'T':
                self.init_device_tmos()
            elif self.dtype == 'P':
                self.init_device_panos()
            else:
                raise RcmdError('ERROR: Unknown device type')

        self.connected = True

        return True


    def os_detect(self):
        got_prompt = False
        output = ''

        # Required to prevent Arista EOS from sending control characters in prompt
        self.do_sendline('terminal length 0')

        self.child.sendline('show version')

        while got_prompt is False:
            myexp = self.child.expect([self.prompt, MORE_PROMPTS, pexpect.EOF, pexpect.TIMEOUT], timeout=self.timeout)
            if myexp == 0:
                output = output + self.child.before
                got_prompt = True
            elif myexp == 1:
                output = output + self.child.before
                self.child.send(' ')
            elif myexp == 2:
                raise RcmdError('ERROR: EOF encountered')
            elif myexp == 3:
                raise RcmdError('ERROR: Timeout encountered')
            else:
                raise RcmdError('ERROR: Unknown expect error')

        if re.search(r'\nJUNOS ', output):
            self.dtype = 'J'
            if self.debug:
                print('\nDEBUG> Juniper JunOS device detected')
            self.init_device_junos()
        elif re.search(r'Arista', output):
            self.dtype = 'A'
            if self.debug:
                print('\nDEBUG> Arista EOS device detected')
            self.init_device_eos()
        elif re.search(r'(Cisco IOS|\ncisco )', output):
            self.dtype = 'C'
            if self.debug:
                print('\nDEBUG> Cisco IOS device detected')
            self.init_device_ios()
        elif re.search(r'Cisco Nexus', output):
            self.dtype = 'N'
            if self.debug:
                print('\nDEBUG> Cisco NX-OS device detected')
            self.init_device_nxos()
        elif re.search(r'Cisco Application Control', output):
            self.dtype = 'E'
            if self.debug:
                print('\nDEBUG> Cisco ACE device detected')
            self.init_device_ace()
        elif re.search(r'\n(Cisco Adaptive Security|FWSM)', output):
            self.dtype = 'F'
            if self.debug:
                print('\nDEBUG> Cisco ASA/FWSM device detected')
            self.init_device_asa()
        else:
            raise RcmdError('ERROR: Unknown device type')

        return True


    def init_device_junos(self):
        self.do_sendline('set cli screen-length 0')
        self.do_sendline('set cli screen-width 0')
        self.child.send(chr(0x1b))
        self.child.send('q')
        self.do_sendline('')
        return True


    def init_device_eos(self):
        self.do_sendline('terminal length 0')
        self.do_sendline('terminal width 32767')
        return True


    def init_device_ios(self):
        self.do_sendline('terminal length 0')
        self.do_sendline('terminal width 0')
        return True


    def init_device_nxos(self):
        self.do_sendline('terminal length 0')
        self.do_sendline('terminal width 511')
        return True


    def init_device_ace(self):
        self.do_sendline('terminal length 0')
        self.do_sendline('terminal width 511')
        return True


    def init_device_asa(self):
        self.do_sendline('terminal pager 0')
        return True


    def init_device_linux(self):
        pass
        return True


    def init_device_tmos(self):
        pass
        return True


    def init_device_panos(self):
        self.do_sendline('set cli pager off')
        self.do_sendline('set cli terminal width 500')
        self.do_sendline('set cli scripting-mode on')
        self.do_sendline('set cli confirmation-prompt off')
        return True


    def dump_hex(self, output):
        out1 = ':'.join('{:02x}'.format(ord(c)) for c in output)
        print(out1)
        return True


    def do_spawn_ssh(self):
        if self.sshconfig is None:
            self.child = pexpect.spawn(SSH, ['-l', self.username, self.ip], encoding='utf-8', codec_errors='ignore')
        else:
            self.child = pexpect.spawn(SSH, ['-F', self.sshconfig, '-l', self.username, self.ip], encoding='utf-8', codec_errors='ignore')
        self.child.maxread = MAXREAD
        if self.debug:
            self.child.logfile_read = sys.stdout
        if self.pki is False:
            self.do_expect(PASSWORD_PROMPT, LOGINTIMEOUT)
            time.sleep(1)
            self.child.sendline(self.password)
        self.do_expect(self.prompt, LOGINTIMEOUT)
        return True


    def do_spawn_telnet(self):
        if self.pserver is None:
            self.child = pexpect.spawn(TELNET, [self.ip], encoding='utf-8', codec_errors='ignore')
        else:
            arglist = ['-,rawer']
            arg2 = f'socks4:{self.pserver}:{self.ip}:23,socksport={self.pport}'
            arglist.append(arg2)
            self.child = pexpect.spawn(SOCAT, arglist, encoding='utf-8', codec_errors='ignore')
        self.child.maxread = MAXREAD
        if self.debug:
            self.child.logfile_read = sys.stdout
        myexp = self.child.expect(['sername:', 'ogin:', pexpect.EOF, pexpect.TIMEOUT], timeout=LOGINTIMEOUT)
        if myexp == 0 or myexp == 1:
            pass
        elif myexp == 2:
            raise RcmdError('ERROR: EOF encountered')
        elif myexp == 3:
            raise RcmdError('ERROR: Timeout encountered')
        else:
            raise RcmdError('ERROR: Unknown expect error')
        self.child.sendline(self.username)
        self.do_expect(PASSWORD_PROMPT, LOGINTIMEOUT)
        time.sleep(1)
        self.child.sendline(self.password)
        self.do_expect(self.prompt, LOGINTIMEOUT)
        return True


    def do_set_prompt(self):
        self.child.sendline('')
        self.do_expect(self.prompt, self.timeout)
        self.prompt = self.child.match.group(0)
        m = re.search(HOST_PROMPT, self.prompt)
        if m.group(1) is not None:
            prompt1 = re.escape(m.group(1))
            self.prompt = rf'\r\n{prompt1}\S*{PROMPT_CHAR}'
        return True


    def do_expect(self, myexpect, mytimeout):
        myexp = self.child.expect([myexpect, pexpect.EOF, pexpect.TIMEOUT], timeout=mytimeout)
        if myexp == 0:
            pass
        elif myexp == 1:
            raise RcmdError('ERROR: EOF encountered')
        elif myexp == 2:
            raise RcmdError('ERROR: Timeout encountered')
        else:
            raise RcmdError('ERROR: Unknown expect error')
        self.buffer = self.child.before
        return True


    def do_expectraw(self, myexpect, mytimeout):
        myexp = self.child.expect([myexpect, pexpect.EOF, pexpect.TIMEOUT], timeout=mytimeout)
        if myexp == 0:
            self.buffer = self.child.before
        return myexp


    def do_sendline(self, line):
        self.child.sendline(line)
        self.do_expect(self.prompt, self.timeout)
        return True


    def do_sendline_noexpect(self, line):
        self.child.sendline(line)
        return True


    def do_sendraw_noexpect(self, line):
        self.child.send(line)
        return True


    def do_sendline_setprompt(self, line):
        self.child.sendline(line)
        self.prompt = BASE_PROMPT
        self.do_expect(self.prompt, self.timeout)
        self.do_set_prompt()
        return True


    def do_getbuffer(self):
        idx = self.buffer.find('\n')
        outp = re.sub('\r\n', '\n', self.buffer[idx+1:])
        return outp


    def disconnect(self):
        self.child.sendline('exit')
        return True
