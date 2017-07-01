#!/bin/env python

# pylint: disable=missing-docstring, locally-disabled, invalid-name, line-too-long, anomalous-backslash-in-string, too-many-arguments, too-many-locals, too-many-branches, too-many-statements

import sys
import time
import re
import ConfigParser
import sqlite3
import pexpect


SSH = '/usr/bin/ssh'
TELNET = '/usr/bin/telnet'
SOCAT = '/usr/bin/socat'
prompt = '[\r\n][\w\d\-\@\/\.\(\)]+[#>]'
passwordPrompt = '[Pp]assword:'
MAXREAD = 4000 * 1024
LOGINTIMEOUT = 30


class Device(object):

    def __init__(self, cfgfile=None, host=None, hostregex=None, customhost=None):
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
        HostList = []
        HostDict = {}

        if (self.host is None) and (self.hostregex is None) and (customhost is None):
            print 'ERROR: No host or hostregex or customhost specified'
            return None

        if self.cfgfile is None:
            print 'ERROR: No cfgfile specified'
            return None

        try:
            cfgf = open(self.cfgfile, 'r')
        except IOError:
            print 'ERROR: Unable to open cfgfile - %s' %(self.cfgfile)
            return None
        cfgf.close()

        config = ConfigParser.ConfigParser()
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
                print 'ERROR: Unable to get DB file from CFG file - %s' %(self.cfgfile)
                return None

            if host is not None:
                db = sqlite3.connect(SQLDB)
                cursor = db.cursor()
                cursor.execute('''SELECT * FROM Devices WHERE Hostname = ? COLLATE NOCASE LIMIT 1''', (host,))
                row = cursor.fetchone()
                if row is None:
                    print 'ERROR: Device does not exist in DB - %s' %(host)
                    return None
                else:
                    self.host = row[0]
                    self.ip = row[1]
                    self.dtype = row[2]
                    self.conn = row[3]
                    self.proxy = int(row[4])
                    self.authid = int(row[5])
            else:
                hostregexsql = 'Hostname NOT NULL'
                for i in self.hostregex:
                    hostregexsql += ' AND Hostname LIKE "%%%s%%"' %(i)

                db = sqlite3.connect(SQLDB)
                cursor = db.cursor()
                sqlquery = 'SELECT * FROM Devices WHERE %s ORDER BY Hostname ASC' %(hostregexsql)
                cursor.execute(sqlquery)
                rows = cursor.fetchall()
                if not rows:
                    print 'ERROR: Device does not exist in DB - %s' %(self.hostregex)
                    return None
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
                        print "%s) %s %s %s" %(str(idx).rjust(4), host.ljust(28), ip.ljust(16), cmethod)
                        idx += 1
                    inidx = raw_input('Enter selection (default is 1, q to quit): ')
                    isvalid = False
                    if inidx == 'q':
                        print 'Exiting'
                        return None
                    else:
                        if inidx == '':
                            inidx = '1'
                        try:
                            inidx = int(inidx)
                        except ValueError:
                            print 'Invalid entry'
                            return None
                        if (inidx >= idx) or (inidx < 1):
                            print 'Invalid entry - no such index'
                            return None
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
                            return None

            db.close()

        authsection = 'Auth' + str(self.authid)

        try:
            include_auth = config.get(authsection, 'include_auth')
        except ConfigParser.NoOptionError:
            self.username = config.get(authsection, 'username')
            self.password = config.get(authsection, 'password')
        else:
            self.username = config.get(include_auth, 'username')
            self.password = config.get(include_auth, 'password')

        try:
            self.enable_password = config.get(authsection, 'enable_password')
        except ConfigParser.NoOptionError:
            self.enable_password = self.password

        if self.proxy != 0:
            self.proxysection = 'Proxy' + str(self.proxy)
            self.pserver = config.get(self.proxysection, 'server')
            self.pport = config.get(self.proxysection, 'port')
            self.sshconfig = config.get(self.proxysection, 'sshconfig')

        self.valid = True

        return None


    def printvars(self):
        '''
        For debugging purpose only.
        '''
        print 'cfgfile == ', self.cfgfile
        print 'host ==', self.host
        print 'hostregex ==', self.hostregex
        print 'ip ==', self.ip
        print 'dtype ==', self.dtype
        print 'conn ==', self.conn
        print 'proxy ==', self.proxy
        print 'authid ==', self.authid
        print 'username ==', self.username
        print 'password ==', self.password
        print 'enable_password ==', self.enable_password


    def connect(self, debug=False, timeout=45):
        self.debug = debug
        self.timeout = timeout

        if self.conn == 'S':
            self.child = self.do_spawn_ssh()
        elif self.conn == 'T':
            self.child = self.do_spawn_telnet()
        else:
            print 'ERROR: Invalid connection type - %s' %(self.host)
            return False
        if self.child is None:
            return False

        if self.dtype == 'C':
            self.do_sendline('terminal length 0')
            self.do_sendline('terminal width 511')
        elif self.dtype == 'N':
            self.do_sendline('terminal length 0')
            self.do_sendline('terminal width 511')
        elif self.dtype == 'J':
            self.do_sendline('set cli screen-length 0')
            self.do_sendline('set cli screen-width 1024')
            self.child.send(chr(0x1b))
            self.child.send('q')
            self.do_sendline('')
        elif self.dtype == 'A':
            self.do_sendline('terminal length 0')
            self.do_sendline('terminal width 511')
        elif self.dtype == 'E':
            self.do_sendline('terminal length 0')
            self.do_sendline('terminal width 511')
        elif self.dtype == 'F':
            self.child.sendline('enable')
            self.do_expect(self.child, passwordPrompt, LOGINTIMEOUT)
            self.child.sendline(self.enable_password)
            self.do_sendline('term pager 0')
        else:
            print 'ERROR: Invalid device type - %s' %(self.host)
            return False

        self.connected = True

        return True


    def do_spawn_ssh(self):
        if self.sshconfig is None:
            mychild = pexpect.spawn(SSH, ['-l', self.username, self.ip])
        else:
            mychild = pexpect.spawn(SSH, ['-F', self.sshconfig, '-l', self.username, self.ip])
        mychild.maxread = MAXREAD
        if self.debug:
            mychild.logfile_read = sys.stdout
        if not self.do_expect(mychild, passwordPrompt, LOGINTIMEOUT):
            return None
        time.sleep(1)
        mychild.sendline(self.password)
        if not self.do_expect(mychild, prompt, LOGINTIMEOUT):
            return None
        return mychild


    def do_spawn_telnet(self):
        if self.pserver is None:
            mychild = pexpect.spawn(TELNET, [self.ip])
        else:
            arglist = ['-,rawer']
            arg2 = 'socks4:%s:%s:23,socksport=%s' %(self.pserver, self.ip, self.pport)
            arglist.append(arg2)
            mychild = pexpect.spawn(SOCAT, arglist)
        mychild.maxread = MAXREAD
        if self.debug:
            mychild.logfile_read = sys.stdout
        myexp = mychild.expect(['sername:', 'ogin:', pexpect.EOF, pexpect.TIMEOUT], timeout=LOGINTIMEOUT)
        if myexp == 0 or myexp == 1:
            pass
        elif myexp == 2:
            print 'ERROR: EOF encountered - %s' %(self.host)
            return None
        elif myexp == 3:
            print 'ERROR: Timeout encountered - %s' %(self.host)
            return None
        else:
            print 'ERROR: Unknown expect error - %s' %(self.host)
            return None
        mychild.sendline(self.username)
        if not self.do_expect(mychild, passwordPrompt, LOGINTIMEOUT):
            return None
        time.sleep(1)
        mychild.sendline(self.password)
        if not self.do_expect(mychild, prompt, LOGINTIMEOUT):
            return None
        return mychild


    def do_expect(self, mychild, myexpect, mytimeout):
        myexp = mychild.expect([myexpect, pexpect.EOF, pexpect.TIMEOUT], timeout=mytimeout)
        if myexp == 0:
            pass
        elif myexp == 1:
            print 'ERROR: EOF encountered - %s' %(self.host)
            return False
        elif myexp == 2:
            print 'ERROR: Timeout encountered - %s' %(self.host)
            return False
        else:
            print 'ERROR: Unknown expect error - %s' %(self.host)
            return False
        self.buffer = mychild.before
        return True


    def do_sendline(self, line):
        self.child.sendline(line)
        if not self.do_expect(self.child, prompt, self.timeout):
            return False
        return True


    def do_getbuffer(self):
        idx = self.buffer.find('\n')
        outp = re.sub('\r\n', '\n', self.buffer[idx+1:])
        return outp


    def disconnect(self):
        self.child.sendline('exit')
        return True
