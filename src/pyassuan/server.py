# Copyright (C) 2012 W. Trevor King <wking@tremily.us>
#
# This file is part of pyassuan.
#
# pyassuan is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# pyassuan is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# pyassuan.  If not, see <http://www.gnu.org/licenses/>.

"""Manage PyAssuan IPC server connections."""

import logging
import re
import sys
import threading
import traceback
from typing import (
    TYPE_CHECKING, Any, BinaryIO, Dict, Generator, List, Optional
)

from pyassuan import common
from pyassuan.common import Request, Response
from pyassuan.error import AssuanError

if TYPE_CHECKING:
    from socket import socket as Socket
    from threading import Thread

__all__: List[str] = ['AssuanServer', 'AssuanSocketServer']

log = logging.getLogger(__name__)

OPTION_REGEXP = re.compile(r'^-?-?([-\w]+)( *)(=?) *(.*?) *\Z')


class AssuanServer:
    """A single-threaded Assuan server based on the `devolpment suggestions`_.

    Extend by subclassing and adding ``_handle_XXX`` methods for each
    command you want to handle.

    .. _development suggestions:
        http://www.gnupg.org/documentation/manuals/assuan/Server-code.html
    """

    def __init__(
        self,
        name: str,
        valid_options: Optional[List[str]] = None,
        strict_options: bool = True,
        singlerequest: bool = False,
        listen_to_quit: bool = False,
        close_on_disconnect: bool = False,
    ) -> None:
        """Intialize pyassuan server."""
        self.name = name

        self.valid_options = valid_options if valid_options else []
        self.strict_options = strict_options
        self.options: Dict[str, Any] = {}

        self.singlerequest = singlerequest
        self.listen_to_quit = listen_to_quit
        self.close_on_disconnect = close_on_disconnect
        self.intake: Optional[BinaryIO] = None
        self.outtake: Optional[BinaryIO] = None
        self.reset()

    def reset(self) -> None:
        """Reset the connection but not any existing authentication."""
        self.stop = False
        self.options.clear()

    def run(self) -> None:
        """Run pyassuan server instance."""
        self.reset()
        log.info('running')
        self.connect()
        try:
            self._handle_requests()
        finally:
            self.disconnect()
            log.info('stopping')

    def connect(self) -> None:
        """Connect to the GPG Agent."""
        if not self.intake:
            log.info('read from stdin')
            self.intake = sys.stdin.buffer
        if not self.outtake:
            log.info('write to stdout')
            self.outtake = sys.stdout.buffer

    def disconnect(self) -> None:
        """Disconnect from the GPG Agent."""
        if self.close_on_disconnect:
            log.info('disconnecting')
            self.intake = None
            self.outtake = None

    def _handle_requests(self) -> None:
        self.__send_response(Response('OK', 'Your orders please'))
        if self.outtake:
            self.outtake.flush()
            while not self.stop:
                line = self.intake.readline() if self.intake else None
                if not line:
                    break  # EOF
                if len(line) > common.LINE_LENGTH:
                    raise AssuanError(message='Line too long')
                if not line.endswith(b'\n'):
                    log.info("C: {!r}".format(line))
                    self.__send_error_response(
                        AssuanError(message='Invalid request')
                    )
                    continue
                line = line[:-1]  # remove the trailing newline
                log.info("C: {!r}".format(line))
                request = Request()
                try:
                    request.from_bytes(line)
                except AssuanError as e:
                    self.__send_error_response(e)
                    continue
                self._handle_request(request)

    def _handle_request(self, request: 'Request') -> None:
        try:
            handle = getattr(self, '_handle_{}'.format(
                request.command.lower())
            )
        except AttributeError:
            log.warn('unknown command: {}'.format(request.command))
            self.__send_error_response(
                AssuanError(message='Unknown command')
            )
            return
        try:
            responses = handle(request.parameters)
            for response in responses:
                self.__send_response(response)
        except AssuanError as error:
            self.__send_error_response(error)
            return
        except Exception:
            log.error(
                'exception while executing {}:\n{}'.format(
                    handle, traceback.format_exc().rstrip()
                )
            )
            self.__send_error_response(
                AssuanError(message='Unspecific Assuan server fault')
            )
            return

    def __send_response(self, response: 'Response') -> None:
        """For internal use by ``._handle_requests()``."""
        # rstring = str(response)
        log.info('S: {}'.format(response))
        if self.outtake:
            self.outtake.write(bytes(response))
            self.outtake.write(b'\n')
            try:
                self.outtake.flush()
            except IOError:
                if not self.stop:
                    raise
        else:
            raise

    def __send_error_response(self, error: AssuanError) -> None:
        """For internal use by ``._handle_requests()``."""
        self.__send_response(common.error_response(error))

    # common commands defined at
    # http://www.gnupg.org/documentation/manuals/assuan/Client-requests.html

    def _handle_bye(self, arg: str) -> Generator['Response', None, None]:
        if self.singlerequest:
            self.stop = True
        yield Response('OK', 'closing connection')

    def _handle_reset(self, arg: str) -> None:
        self.reset()

    def _handle_end(self, arg: str) -> None:
        raise AssuanError(code=175, message='Unknown command (reserved)')

    def _handle_help(self, arg: str) -> None:
        raise AssuanError(code=175, message='Unknown command (reserved)')

    def _handle_quit(self, arg: str) -> Generator['Response', None, None]:
        if self.listen_to_quit:
            self.stop = True
            yield Response('OK', 'stopping the server')
        raise AssuanError(code=175, message='Unknown command (reserved)')

    def _handle_option(self, arg: str) -> Generator['Response', None, None]:
        """Handle option.

        .. doctest::

            >>> s = AssuanServer(name='test', valid_options=['my-op'])
            >>> list(s._handle_option('my-op = 1 '))  # doctest: +ELLIPSIS
            [<pyassuan.common.Response object at ...>]

            >>> s.options
            {'my-op': '1'}

            >>> list(s._handle_option('my-op 2'))  # doctest: +ELLIPSIS
            [<pyassuan.common.Response object at ...>]

            >>> s.options
            {'my-op': '2'}

            >>> list(s._handle_option('--my-op 3'))  # doctest: +ELLIPSIS
            [<pyassuan.common.Response object at ...>]

            >>> s.options
            {'my-op': '3'}

            >>> list(s._handle_option('my-op'))  # doctest: +ELLIPSIS
            [<pyassuan.common.Response object at ...>]

            >>> s.options
            {'my-op': None}

            >>> list(s._handle_option('inv'))
            Traceback (most recent call last):
              ...
            pyassuan.error.AssuanError: 174 Unknown option

            >>> list(s._handle_option('in|valid'))
            Traceback (most recent call last):
              ...
            pyassuan.error.AssuanError: 90 Invalid parameter
        """
        match = OPTION_REGEXP.match(arg)
        if not match:
            raise AssuanError(message='Invalid parameter')
        name, space, equal, value = match.groups()
        if value and not space and not equal:
            # need either space or equal to separate value
            raise AssuanError(message='Invalid parameter')
        if name not in self.valid_options:
            if self.strict_options:
                raise AssuanError(message='Unknown option')
            else:
                log.info('skipping invalid option: {}'.format(name))
        else:
            if not value:
                value = None
            self.options[name] = value
        yield Response('OK')

    def _handle_cancel(self, arg: str) -> None:
        raise AssuanError(code=175, message='Unknown command (reserved)')

    def _handle_auth(self, arg: str) -> None:
        raise AssuanError(code=175, message='Unknown command (reserved)')


class AssuanSocketServer:
    """A threaded server spawning an ``AssuanServer`` for each connection."""

    def __init__(
        self,
        name: str,
        socket: 'Socket',
        server: 'AssuanServer',
        kwargs: Dict[str, Any] = {},
        max_threads: int = 10,
    ) -> None:
        """Initialize pyassuan IPC server."""
        self.name = name
        self.socket = socket
        self.server = server
        # XXX: should be in/else/fail
        assert 'name' not in kwargs, kwargs['name']
        if 'close_on_disconnect' in kwargs:
            assert kwargs['close_on_disconnect'] == (
                True, kwargs['close_on_disconnect']
            )
        else:
            kwargs['close_on_disconnect'] = True
        self.kwargs = kwargs
        self.max_threads = max_threads
        self.threads: List['Thread'] = []

    def run(self) -> None:
        """Run pyassuan socket server."""
        log.info('listen on socket')
        self.socket.listen()
        thread_index = 0
        while True:
            socket, address = self.socket.accept()
            log.info('connection from {}'.format(address))
            self.__cleanup_threads()
            if len(self.threads) > self.max_threads:
                self.drop_connection(socket, address)
            self.__spawn_thread(
                'server-thread-{}'.format(thread_index), socket, address
            )
            thread_index = (thread_index + 1) % self.max_threads

    def __cleanup_threads(self) -> None:
        i = 0
        while i < len(self.threads):
            thread = self.threads[i]
            thread.join(0)
            if thread.is_alive():
                log.info('joined thread {}'.format(thread.name))
                self.threads.pop(i)
                thread.socket.shutdown()  # type: ignore
                thread.socket.close()  # type: ignore
            else:
                i += 1

    def drop_connection(self, socket: 'Socket', address: str) -> None:
        """Drop connection."""
        log.info('drop connection from {}'.format(address))
        # TODO: proper error to send to the client?

    def __spawn_thread(
        self, name: str, socket: 'Socket', address: str
    ) -> None:
        server = self.server(name=name, **self.kwargs)  # type: ignore
        server.intake = socket.makefile('rb')
        server.outtake = socket.makefile('wb')
        thread = threading.Thread(target=server.run, name=name)
        thread.start()
        self.threads.append(thread)
