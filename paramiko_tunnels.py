import paramiko
import SocketServer
import socket
import select
import threading

class SSHConnection(object):
    """
    An ssh connection
    """

    def __init__(self, host, port, username, password):
        """

        :param host:
        :param port:
        :param username:
        :param password:
        :return:
        """
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(
            host,
            port=port,
            username=username,
            password=password)

        # Tunnel info
        self.tunnel_channel = None
        self.forward_server_threads = {}

    def add_tunnel(self, remote_host, remote_port, local_port=None):
        """
        Create a tunnel using the SSH transport of this connection

        :param remote_host: host that we want to tunnel to
        :param remote_port: port that we want to tunnel to
        :param local_port: port to listen for connections on. You should know
            the port is available if you set this parameter.
        :return: The local port the tunnel is listening on
        """

        if local_port is None:
            local_port = self._get_available_local_port()

        # this is a little convoluted - it give the handler the info it needs
        # to create channel the SSH transport and forward packets to it.
        # SocketServer doesn't give Handlers any way to access the outer
        # server normally, so we can't just set the port and transport values
        # when we create the server - it has to eb part of the handler class.
        class SubHandler (ForwardHandler):
            chain_host = remote_host
            chain_port = remote_port
            ssh_transport = self.ssh.get_transport()

        forward_server = ForwardServer(('', local_port), SubHandler)
        forward_server_thread = ServerThread(forward_server)
        forward_server_thread.start()
        self.forward_server_threads[
            (remote_host, remote_port, local_port)] = forward_server_thread

        return local_port

    def shutdown_tunnels(self):
        """
        Shutdown all active tunnels
        :return:
        """
        for k, thread in self.forward_server_threads.items():
            thread.shutdown()
            thread.join()


    def shutdown_tunnel(self, address):
        """
        Shutdown a specific tunnel

        :param address: tuple of (remote IP, remote port, local port)
        :return:
        """
        thread = self.forward_server_threads[address]
        thread.shutdown()
        thread.join()


    @staticmethod
    def _get_available_local_port():
        """
        Get the OS to provide an arbitrary available port

        :returns: A port number as an int
        """
        # Create a socket to get an arbitrary port
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Bind to port 0 so the SO can choose an available one
        s.bind(('127.0.0.1', 0))
        # Get port number
        port = s.getsockname()[1]
        # Close the socket, as we will not use it anymore
        s.close()

        return port

class ForwardServer(SocketServer.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

class ForwardHandler(SocketServer.BaseRequestHandler):

    def handle(self):
        chan = self.ssh_transport.open_channel(
            'direct-tcpip',
            (self.chain_host, self.chain_port),
            self.request.getpeername())

        print('Connected!  Tunnel open %r -> %r -> %r' % (self.request.getpeername(),
                                                            chan.getpeername(), (self.chain_host, self.chain_port)))
        while True:
            r, w, x = select.select([self.request, chan], [], [])
            if self.request in r:
                data = self.request.recv(1024)
                if len(data) == 0:
                    break
                chan.send(data)
            if chan in r:
                data = chan.recv(1024)
                if len(data) == 0:
                    break
                self.request.send(data)

        peername = self.request.getpeername()
        chan.close()
        self.request.close()
        print('Tunnel closed from %r' % (peername,))

class ServerThread(threading.Thread):

    def __init__(self, server):
        super(ServerThread, self).__init__()
        self.server = server

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        print 'shutting down server'
        self.server.shutdown()


