#
# signalreceiver.py
#
# Copyright (C) 2007, 2008 Andrew Resch <andrewresch@gmail.com>
#
# Deluge is free software.
#
# You may redistribute it and/or modify it under the terms of the
# GNU General Public License, as published by the Free Software
# Foundation; either version 3 of the License, or (at your option)
# any later version.
#
# deluge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with deluge.    If not, write to:
# 	The Free Software Foundation, Inc.,
# 	51 Franklin Street, Fifth Floor
# 	Boston, MA    02110-1301, USA.
#


import sys
import socket
import random

import gobject

from deluge.ui.client import aclient as client
import deluge.SimpleXMLRPCServer as SimpleXMLRPCServer
from SocketServer import ThreadingMixIn
import deluge.xmlrpclib as xmlrpclib
import threading
import socket

from deluge.log import LOG as log

class SignalReceiver(SimpleXMLRPCServer.SimpleXMLRPCServer):

    def __init__(self):
        log.debug("SignalReceiver init..")
        # Set to true so that the receiver thread will exit

        self.signals = {}

        self.remote = False

        self.start_server()

    def start_server(self, port=None):
        # Setup the xmlrpc server
        host = "127.0.0.1"
        if self.remote:
            host = ""

        server_ready = False
        while not server_ready:
            if port:
                _port = port
            else:
                _port = random.randint(40000, 65535)
            try:
                SimpleXMLRPCServer.SimpleXMLRPCServer.__init__(
                    self, (host, _port), logRequests=False, allow_none=True)
            except socket.error, e:
                log.debug("Trying again with another port: %s", e)
            except:
                log.error("Could not start SignalReceiver XMLRPC server: %s", e)
                sys.exit(0)
            else:
                self.port = _port
                server_ready = True

        # Register the emit_signal function
        self.register_function(self.emit_signal)

        self.socket.setblocking(False)

        gobject.io_add_watch(self.socket.fileno(), gobject.IO_IN | gobject.IO_OUT | gobject.IO_PRI | gobject.IO_ERR | gobject.IO_HUP, self._on_socket_activity)
        #gobject.timeout_add(50, self.handle_signals)

    def _on_socket_activity(self, source, condition):
        """This gets called when there is activity on the socket, ie, data to read
        or to write."""
        self.handle_request()
        return True

    def shutdown(self):
        """Shutdowns receiver thread"""
        log.debug("Shutting down signalreceiver")
        # De-register with the daemon so it doesn't try to send us more signals
        try:
            client.deregister_client()
            client.force_call()
        except Exception, e:
            log.debug("Unable to deregister client from server: %s", e)

    def set_remote(self, remote):
        self.remote = remote
        self.start_server(self.port)

    def run(self):
        """This gets called when we start the thread"""
        # Register the signal receiver with the core
        client.register_client(str(self.port))

    def get_port(self):
        """Get the port that the SignalReceiver is listening on"""
        return self.port

    def emit_signal(self, signal, *data):
        """Exported method used by the core to emit a signal to the client"""
        try:
            for callback in self.signals[signal]:
                gobject.idle_add(callback, *data)

        except Exception, e:
            log.warning("Unable to call callback for signal %s: %s", signal, e)

    def connect_to_signal(self, signal, callback):
        """Connect to a signal"""
        try:
            if callback not in self.signals[signal]:
                self.signals[signal].append(callback)
        except KeyError:
            self.signals[signal] = [callback]
