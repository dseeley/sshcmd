# sshcmd
Runs a command on a remote host (via paramiko).

Operates in two modes:
+ exec_command
  + Executes the command directly.
+ sendall
  + Executes the command via a shell.  Sometimes needed when the exec_command version is not fully supported, (e.g. some Cisco devices)

Returns the output as a string.

## Invocation
e.g.:
```python
import sshcmd

cnx = sshcmd.SSHCmdExec(hostname='192.168.0.1', username='username', pkeyfile='./id_rsa')
print cnx.exec_command("ls -la /etc/")

cnx = sshcmd.SSHCmdSendAll(hostname='192.168.0.1', username='username', password='userpass')
cnx.send_command("terminal length 0")       # Disable paging (e.g. for Cisco devices)
print cnx.send_command("ls -la /var/")
```

## Requirements
+ python 2.7
+ paramiko
