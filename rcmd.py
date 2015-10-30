#!/usr/bin/env python

# pylint: disable=missing-docstring, locally-disabled, invalid-name, line-too-long, anomalous-backslash-in-string

import sys
import re
import getopt
import ConfigParser
import sqlite3
import pexpect

SSH = '/usr/bin/ssh'
TELNET = '/usr/bin/telnet'
logfile = 'NULL'
timeout = 30
dumpio = 0
prompt = '[\r\n][\w\d\-\@]+[#>]'
MAXREAD = 4000 * 1024


def usage():
    print 'Usage:\n\t', sys.argv[0], '-c cmdfile -i cfgfile [options] host'
    print '''
        -c cmdfile      Commands file
        -i cfgfile      Config file
        host            Hostname of device to connect to (MUST exist in device DB)

        Options:
        -d              Dump all in/output from beginning
        -l logfile      Define a logfile to send output to
        -t timeout      Define timeout for commands (default 30 seconds)
'''
    sys.exit(2)

def do_spawn_ssh(myip, myusername, mypassword, mysshconfig=''):
    if mysshconfig != '':
        mychild = pexpect.spawn(SSH, ['-F', mysshconfig, '-l', myusername, myip])
    else:
        mychild = pexpect.spawn(SSH, ['-l', myusername, myip])
    mychild.maxread = MAXREAD
    if dumpio == 1:
        mychild.logfile_read = sys.stdout
    do_expect(mychild, '[Pp]assword[: ]', 10)
    mychild.sendline(mypassword)
    return mychild

def do_spawn_telnet(myip, myusername, mypassword):
    mychild = pexpect.spawn(TELNET, [myip])
    mychild.maxread = MAXREAD
    if dumpio == 1:
        mychild.logfile_read = sys.stdout
    do_expect(mychild, 'sername:', 10)
    mychild.sendline(myusername)
    do_expect(mychild, '[Pp]assword[: ]', 10)
    mychild.sendline(mypassword)
    return mychild

def do_expect(mychild, myexpect, mytimeout):
    myexp = mychild.expect([myexpect, pexpect.EOF, pexpect.TIMEOUT], timeout=mytimeout)
    if myexp == 0:
        pass
    elif myexp == 1:
        print 'EOF encountered'
        sys.exit(1)
    elif myexp == 2:
        print 'Timeout encountered'
        sys.exit(1)
    else:
        print 'Unknown error'
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
        timeout = arg
    elif opt == '-d':
        dumpio = 1
    else:
        usage()

if len(args) != 1:
    usage()

host = args[0]

try:
    cmdf = open(cmdfile, 'r')
except IOError:
    print 'ERROR: Unable to open cmdfile'
    sys.exit(2)

try:
    cfgf = open(cfgfile, 'r')
except IOError:
    print 'ERROR: Unable to open cfgfile'
    sys.exit(2)
cfgf.close()

config = ConfigParser.ConfigParser()
config.read(cfgfile)

SQLDB = config.get('DevicesDB', 'path')
if SQLDB == None:
    print 'ERROR: Unable to get DB file from CFG file'
    sys.exit(2)

db = sqlite3.connect(SQLDB)
cursor = db.cursor()
cursor.execute('''SELECT * FROM Devices WHERE Hostname = ? COLLATE NOCASE LIMIT 1''', (host,))
row = cursor.fetchone()
if row == None:
    print 'ERROR: Device does not exist in DB'
    sys.exit(2)
else:
    host = row[0]
    ip = row[1]
    dtype = row[2]
    conn = row[3]
    proxy = row[4]
    authid = row[5]
db.close()

authsection = 'Auth' + str(authid)
username = config.get(authsection, 'username')
password = config.get(authsection, 'password')

if proxy != 0:
    proxysection = 'Proxy' + str(proxy)
    sshconfig = config.get(proxysection, 'sshconfig')

if conn == 'S':
    if proxy != 0:
        child = do_spawn_ssh(ip, username, password, sshconfig)
    else:
        child = do_spawn_ssh(ip, username, password)
elif conn == 'T':
    if proxy != 0:
        print 'Proxy with Telnet not supported yet'
        sys.exit(1)
    else:
        child = do_spawn_telnet(ip, username, password)
elif conn == 'F':
    print 'Cisco Firewalls not supported yet'
    sys.exit(1)
else:
    print 'Invalid connection type'
    sys.exit(1)

do_expect(child, prompt, timeout)

if dtype == 'C':
    child.sendline('term len 0')
    do_expect(child, prompt, timeout)
elif dtype == 'J':
    child.sendline('set cli screen-length 0')
    do_expect(child, prompt, timeout)
    child.send(chr(0x1b))
    child.send('q')
elif dtype == 'A':
    child.sendline('term len 0')
    do_expect(child, prompt, timeout)
else:
    print 'Invalid device type'
    sys.exit(1)

child.sendline('')

if logfile != 'NULL':
    try:
        fout = open(logfile, 'wb')
    except IOError:
        print 'Error opening logfile'
        sys.exit(1)
    child.logfile_read = fout

for cmd in cmdf:
    line = cmd.rstrip()
    if re.search('^[^#!]', line):
        do_expect(child, prompt, timeout)
        child.sendline(line)

do_expect(child, prompt, timeout)
child.sendline('exit')

print
print '!!! Completed %s (%s) !!!' %(host, ip)
