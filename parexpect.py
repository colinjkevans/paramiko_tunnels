import paramiko

class Spawn:
    """
    An ssh client that will have the same interface as a pexpect Spawn
    :return:
    """

    def __init__(self, host, port, username, password, prompt='# '):

        self.prompt = prompt
        self.before = ''
        self.shell = None

        self.ssh = paramiko.SSHClient()
        self.ssh.load_system_host_keys()
        # This should probably be changed because we don't want to add keys
        # if we're connecting to the local side of a tunnel
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(host, username=username, password=password, port=port)

        # We need a shell if this is going to look like pexpect
        self.invoke_shell()

    def invoke_shell(self):
        self.shell = self.ssh.invoke_shell()
        self.expect(self.prompt)

    def sendline(self, line):
        self.shell.send(line + '\n')

    def expect(self, pattern):
        self.before = ''
        while not self.before.endswith(pattern):
            outp = self.shell.recv(1024)
            print(outp)
            self.before += outp

        return 0