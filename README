rcmd.py
=======

Python script to run a list of commands on remote network devices.

Tested on Cisco IOS, NX-OS, ASA, ACE, Arista EOS and Juniper JunOS devices.

Usage:
```
        rcmd.py -c cmdfile -i cfgfile [options] host

        -c cmdfile      Commands file
        -i cfgfile      Config file
        host            Hostname of device to connect to (MUST exist in device DB)

        Options:
        -d              Debug mode
        -a              Autodetect OS
        -e              Enter enable mode
        -h <host,...>   Define a custom host entry to use. The format is hostname,IP,type,method,proxy,auth
                            hostname - hostname of custom host
                            IP - management IP to connect to custom host
                            type - device type. C=Cisco IOS, N=Cisco NX-OS, E=Cisco ACE, F=Cisco ASA/FWSM Firewall, J=Juniper JunOS, A=Arista EOS
                            method - connection method. S=SSH, T=telnet
                            proxy - proxy ID to use
                            auth - auth ID to use
        -l logfile      Define a logfile to send output to
        -t timeout      Define timeout for commands (default 45 seconds)
```

Command file - text file containing list of commands to run. e.g.

```
show clock
show version
show ip int brief | e unas
```

Due to the way the script works with exact prompt detection, whenever a CLI command changes the prompt (e.g. conf t, configure, etc...), the script will timeout waiting for the previous prompt it already knows. To handle commands that changes the prompt, please put an asterisk character "*" on the line by itself before the command that changes the prompt e.g.

```
*
conf t
hostname R1
*
end
```

Config file - Config file containing credentials, SOCKS proxy configs and location of device DB. e.g.

```
[Auth1]
username=<USER1>
password=<PASSWORD1>

[Auth2]
username=<USER2>
password=<PASSWORD2>

[Auth3]
username=<USER3>
password=<PASSWORD3>

[Auth4]
include_auth=Auth1
enable_password=<PASSWORD4>

[Proxy1]
server=127.0.0.1
port=4001
sshconfig=<PATH_TO_SSH_PROXY_CONFIG>

[Proxy2]
server=127.0.0.1
port=4002
sshconfig=<PATH_TO_SSH_PROXY_CONFIG>

[DevicesDB]
path=<PATH_TO_DEVICES_DB>
```

<SSH_PROXY_CONFIG> - ssh config file with ProxyCommand. e.g.

```
StrictHostKeyChecking no
ProxyCommand /usr/bin/nc -x 127.0.0.1:4001 %h %p
```

<DEVICE_DB> - Sqlite3 DB with devices information. Table created using following SQL command :-

```
CREATE TABLE Devices ( 
    Hostname   TEXT PRIMARY KEY ASC
                    NOT NULL
                    UNIQUE,
    MgmtIP     TEXT NOT NULL
                    UNIQUE,
    DeviceType TEXT NOT NULL,
    ConnMethod TEXT NOT NULL,
    ProxyID    INT  NOT NULL,
    AuthID     INT 
);
```

    Hostname - Unique hostname of device
    MgmtIP - Unique IP address of device
    DeviceType - C = Cisco IOS, N = Cisco NX-OS, E = Cisco ACE, F = Cisco ASA/FWSM Firewall, J = Juniper JunOS, A = Arista EOS
    ConnMethod - S - SSH, T - Telnet
    ProxyID - number to indicate which [Proxy#] section to use in config file. 0 for no proxy.
    AuthID - number to indicate which [Auth#] section to use in config file.
