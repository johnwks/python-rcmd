#!/usr/bin/env python

# pylint: disable=missing-docstring, locally-disabled, invalid-name, line-too-long, anomalous-backslash-in-string


import sys
import re
import getopt
import ConfigParser
import sqlite3
import pexpect
import os
import time

SSH = '/usr/bin/ssh'
TELNET = '/usr/bin/telnet'
SOCAT = '/usr/bin/socat'
logfile = ''
timeout = 45
dumpio = 0
prompt = '[\r\n][\w\d\-\@\/]+[#>]'
passwordPrompt = '[Pp]assword:'
MAXREAD = 4000 * 1024
LOGINTIMEOUT = 30


def usage():
    print 'Usage:\n\t', sys.argv[0], '-c cmdfile -i cfgfile [options] host'
    print '''
        -c cmdfile      Commands file
        -i cfgfile      Config file
        host            Hostname of device to connect to (MUST exist in device DB)

        Options:
        -d              Dump all in/output from beginning
        -l logfile      Define a logfile to send output to
        -t timeout      Define timeout for commands (default 45 seconds)
'''
    sys.exit(1)

def do_spawn_ssh(myip, myusername, mypassword, mysshconfig=''):
    if mysshconfig != '':
        mychild = pexpect.spawn(SSH, ['-F', mysshconfig, '-l', myusername, myip])
    else:
        mychild = pexpect.spawn(SSH, ['-l', myusername, myip])
    mychild.maxread = MAXREAD
    if dumpio == 1:
        mychild.logfile_read = sys.stdout
    do_expect(mychild, passwordPrompt, LOGINTIMEOUT)
    time.sleep(1)
    mychild.sendline(mypassword)
    return mychild

def do_spawn_telnet(myip, myusername, mypassword, mypserver='', mypport=''):
    if mypserver == '':
        mychild = pexpect.spawn(TELNET, [myip])
    else:
        arglist = ['-,rawer']
        arg2 = 'socks4:%s:%s:23,socksport=%s' %(mypserver, myip, mypport)
        arglist.append(arg2)
        mychild = pexpect.spawn(SOCAT, arglist)
    mychild.maxread = MAXREAD
    if dumpio == 1:
        mychild.logfile_read = sys.stdout
    myexp = mychild.expect(['sername:', 'ogin:', pexpect.EOF, pexpect.TIMEOUT], timeout=LOGINTIMEOUT)
    if myexp == 0 or myexp == 1:
        pass
    elif myexp == 2:
        print 'ERROR: EOF encountered - %s' %(host)
        sys.exit(1)
    elif myexp == 3:
        print 'ERROR: Timeout encountered - %s' %(host)
        sys.exit(1)
    else:
        print 'ERROR: Unknown expect error - %s' %(host)
        sys.exit(1)
    mychild.sendline(myusername)
    do_expect(mychild, passwordPrompt, LOGINTIMEOUT)
    time.sleep(1)
    mychild.sendline(mypassword)
    return mychild

def do_expect(mychild, myexpect, mytimeout):
    myexp = mychild.expect([myexpect, pexpect.EOF, pexpect.TIMEOUT], timeout=mytimeout)
    if myexp == 0:
        pass
    elif myexp == 1:
        print 'ERROR: EOF encountered - %s' %(host)
        sys.exit(1)
    elif myexp == 2:
        print 'ERROR: Timeout encountered - %s' %(host)
        sys.exit(1)
    else:
        print 'ERROR: Unknown expect error - %s' %(host)
        sys.exit(1)
    return True


try:
    opts, args = getopt.getopt(sys.argv[1:], 'c:i:l:t:d')
except getopt.GetoptError:
    usage()

for opt, arg in opts:
    if opt == '-c':
        cmdfile = arg
    elif opt == '-i':
        cfgfile = arg
    elif opt == '-l':
        logfile = arg
    elif opt == '-t':
        timeout = int(arg)
    elif opt == '-d':
        dumpio = 1
    else:
        usage()

if len(args) != 1:
    usage()

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
    cfgf = open(cfgfile, 'r')
except IOError:
    print 'ERROR: Unable to open cfgfile - %s' %(host)
    sys.exit(1)
cfgf.close()

config = ConfigParser.ConfigParser()
config.read(cfgfile)

SQLDB = config.get('DevicesDB', 'path')
if SQLDB == None:
    print 'ERROR: Unable to get DB file from CFG file - %s' %(host)
    sys.exit(1)

db = sqlite3.connect(SQLDB)
cursor = db.cursor()
cursor.execute('''SELECT * FROM Devices WHERE Hostname = ? COLLATE NOCASE LIMIT 1''', (host,))
row = cursor.fetchone()
if row == None:
    print 'ERROR: Device does not exist in DB - %s' %(host)
    sys.exit(1)
else:
    host = row[0]
    ip = row[1]
    dtype = row[2]
    conn = row[3]
    proxy = row[4]
    authid = row[5]
db.close()

authsection = 'Auth' + str(authid)

try:
    include_auth = config.get(authsection, 'include_auth')
except ConfigParser.NoOptionError:
    username = config.get(authsection, 'username')
    password = config.get(authsection, 'password')
else:
    username = config.get(include_auth, 'username')
    password = config.get(include_auth, 'password')

try:
    enable_password = config.get(authsection, 'enable_password')
except ConfigParser.NoOptionError:
    enable_password = password

if proxy != 0:
    proxysection = 'Proxy' + str(proxy)
    pserver = config.get(proxysection, 'server')
    pport = config.get(proxysection, 'port')
    sshconfig = config.get(proxysection, 'sshconfig')

os.environ['TERM'] = 'vt100'

if conn == 'S':
    if proxy != 0:
        child = do_spawn_ssh(ip, username, password, sshconfig)
    else:
        child = do_spawn_ssh(ip, username, password)
elif conn == 'T':
    if proxy != 0:
        child = do_spawn_telnet(ip, username, password, pserver, pport)
    else:
        child = do_spawn_telnet(ip, username, password)
else:
    print 'ERROR: Invalid connection type - %s' %(host)
    sys.exit(1)

do_expect(child, prompt, timeout)

if dtype == 'C':
    child.sendline('term len 0')
elif dtype == 'J':
    child.sendline('set cli screen-length 0')
    do_expect(child, prompt, timeout)
    child.send(chr(0x1b))
    child.send('q')
    child.sendline('')
elif dtype == 'A':
    child.sendline('term len 0')
elif dtype == 'F':
    child.sendline('enable')
    do_expect(child, passwordPrompt, LOGINTIMEOUT)
    child.sendline(enable_password)
    child.sendline('term pager 0')
else:
    print 'ERROR: Invalid device type - %s' %(host)
    sys.exit(1)

do_expect(child, prompt, timeout)
child.sendline('')

if logfile != '':
    try:
        fout = open(logfile, 'wb')
    except IOError:
        print 'ERROR: Error opening logfile - %s' %(host)
        sys.exit(1)
    child.logfile_read = fout

for cmd in cmdf:
    line = cmd.rstrip()
    if re.search('^[^#!]', line):
        do_expect(child, prompt, timeout)
        child.sendline(line)

do_expect(child, prompt, timeout)

# Send CR-LF to ensure buffer is flushed before exiting.
child.sendline('')
do_expect(child, prompt, timeout)

child.sendline('exit')

print
print '!!! Completed %s (%s) !!!' %(host, ip)
