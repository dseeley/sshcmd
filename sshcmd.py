#!/usr/bin/python -u

import re
import time
import socket
import select
import paramiko
import sys

# paramiko.util.log_to_file("paramiko.log")

MAX_BUFFER = 65535
BACKSPACE_CHAR = '\x08'


# This represents a simple paramiko ssh connection to 'hostname'
class SSHCmd(object):
    def __init__(self, hostname, username=None, password=None, pkeyfile=None):
        self.hostname = hostname
        self.pkeyfile = pkeyfile
        self.remote_conn_client = None

        # Create instance of SSHClient object
        self.remote_conn_client = paramiko.SSHClient()
        self.remote_conn_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # initiate SSH connection
        try:
            if password:
                self.remote_conn_client.connect(hostname=hostname, username=username, password=password, timeout=10, look_for_keys=False, allow_agent=False)
            elif pkeyfile:
                self.remote_conn_client.connect(hostname=hostname, username=username, key_filename=pkeyfile, timeout=10, look_for_keys=False, allow_agent=False)
        except socket.error as sock_err:
            print "Connection timed-out to " + hostname  # + "\n\n" + str(sock_err)
            exit(1)
        except paramiko.ssh_exception.AuthenticationException as auth_err:
            print "Authentication failure, unable to connect to " + hostname + " as " + username  # + "\n\n" + str(auth_err)
            exit(1)
        except:
            print "Unexpected error: ", sys.exc_info()[0]
            raise

        # print("SSH connection established to " + hostname + " as " + username)


# Executes a command on the remote host.
class SSHCmdExec(SSHCmd):
    def exec_command(self, command_string):
        recv_buf = ''
        # print("Command is: {0}".format(command_string))

        stdin, stdout, stderr = self.remote_conn_client.exec_command(command_string)

        # Wait for the command to terminate, then grab the result
        if stdout.channel.recv_exit_status() == 0:
            # Only print data if there is data to read in the channel
            while stdout.channel.recv_ready():
                rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
                if len(rl) > 0:
                    recv_buf += stdout.channel.recv(1024)
            return recv_buf
        else:
            return "*** CMD (" + command_string + ") FAILED ***"


# Executes commands via a shell.  Needed for some non-standard devices (e.g. some Cisco devices).  Generally much slower than exec_command.
class SSHCmdSendAll(SSHCmd):
    def __init__(self, **kwds):
        super(SSHCmdSendAll, self).__init__(**kwds)
        self.remote_conn_sh = None
        self.cmdPrompt = ""

        self.remote_conn_sh = self.remote_conn_client.invoke_shell()
        self.remote_conn_sh.setblocking(0)
        self.remote_conn_sh.settimeout(5)

        # Flush output (may contain prompt, may not (e.g. Cisco terminal)
        i = 0
        while i <= 50:
            if self.remote_conn_sh.recv_ready():
                self.remote_conn_sh.recv(MAX_BUFFER).decode('utf-8', 'ignore')
            else:
                time.sleep(0.5)
                if not self.remote_conn_sh.recv_ready():
                    break
            i += 1

        # Get the prompt.  We use the presence of this in all future commands to confirm that they have finished (it is the last thing sent)
        self.remote_conn_sh.sendall("\n")
        i = 0
        while i <= 50:
            if self.remote_conn_sh.recv_ready():
                self.cmdPrompt = self.remote_conn_sh.recv(MAX_BUFFER).decode('utf-8', 'ignore')
            else:
                time.sleep(0.5)  # Safeguard to make sure really done
                if self.cmdPrompt and not self.remote_conn_sh.recv_ready():
                    break
            i += 1

        # Remove leading newline
        self.cmdPrompt = re.sub(r"^[\r\n]+(.*)$", r'\1', self.cmdPrompt, flags=re.MULTILINE)

    def send_command(self, command_string):
        recv_buf = ''
        # print("Command is: {0}".format(command_string))

        # Normalise string to remove trailing carriage returns, then add one back.
        self.remote_conn_sh.sendall(command_string.rstrip("[\r\n]*") + "\n")
        i = 0
        while i <= 50:
            if self.remote_conn_sh.recv_ready():
                recv_buf += self.remote_conn_sh.recv(MAX_BUFFER).decode('utf-8', 'ignore')
            else:
                time.sleep(0.2)  # Wait for a small time
                if self.cmdPrompt in recv_buf and not self.remote_conn_sh.recv_ready():
                    break
            i += 1

        # Check for line wrap (remove backspaces)
        if BACKSPACE_CHAR in recv_buf:
            recv_buf = recv_buf.replace(BACKSPACE_CHAR, '')
            output_lines = recv_buf.split("\n")
            new_output = "\n".join(output_lines[1:])
            normalised_output = new_output
        else:
            # Strip command_string from output string
            command_length = len(command_string)
            normalised_output = recv_buf[command_length:]

        # Remove trailing cmdPrompt
        normalised_output = re.sub(r"^(.*?)" + re.escape(self.cmdPrompt) + r"$", r'\1', normalised_output, flags=re.DOTALL)

        # Strip any line endings from the beginning and the prompt at the end
        normalised_output_match = re.search("^[\r\n]*(.*)(?:\r\n|\r|\n).*?#.*", normalised_output, flags=re.DOTALL)
        if normalised_output_match and len(normalised_output_match.groups()):
            normalised_output = normalised_output_match.group(1)

        # Change \r\n to \n
        normalised_output = normalised_output.replace("\r\n", "\n")

        return normalised_output
