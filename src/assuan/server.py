# Copyright (C) 2012 W. Trevor King <wking@tremily.us>
#
# This file is part of assuan.
#
# assuan is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# assuan is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# assuan.  If not, see <http://www.gnu.org/licenses/>.

"""Manage PyAssuan IPC server connections."""

import logging
import re
import sys
import threading
import traceback
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    BinaryIO,
    Dict,
    Generator,
    List,
    Optional,
)

from assuan import common
from assuan.common import Request, Response
from assuan.exception import AssuanError

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
        **kwargs: Any,
    ) -> None:
        """Intialize assuan server."""
        self.name = name

        self.options: Dict[str, Any] = {}
        self.valid_options = valid_options if valid_options else []

        self.strict_options = kwargs.get('strict_options', True)
        self.single_request = kwargs.get('single_request', False)
        self.listen_to_quit = kwargs.get('listen_to_quit', False)
        self.close_on_disconnect = kwargs.get('close_on_disconnect', False)

        self.intake: Optional[BinaryIO] = None
        self.outtake: Optional[BinaryIO] = None

        self.stop = False
        self.reset()

    def __enter__(self) -> 'AssuanServer':
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: Optional[type[AssuanError]],
        exc_value: Optional[AssuanError],
        exc_traceback: TracebackType,
    ) -> None:
        self.disconnect()

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

    def reset(self) -> None:
        """Reset the connection but not any existing authentication."""
        self.stop = False
        self.options.clear()

    def run(self) -> None:
        """Run assuan server instance."""
        self.reset()
        log.info('running')
        self.connect()
        try:
            self._handle_requests()
        finally:
            self.disconnect()
            log.info('stopping')

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
                    log.info("C: %r", line)
                    self.__send_error_response(
                        AssuanError(message='Invalid request')
                    )
                    continue
                line = line.rstrip()  # remove the trailing newline
                log.info("C: %r", line)
                request = Request()
                try:
                    request.from_bytes(line)
                except AssuanError as err:
                    self.__send_error_response(err)
                    continue
                self._handle_request(request)

    def _handle_request(self, request: 'Request') -> None:
        try:
            handle = getattr(self, f"_handle_{request.command.lower()}")
        except AttributeError:
            log.warning('unknown command: %s', request.command)
            self.__send_error_response(AssuanError(message='Unknown command'))
            return

        try:
            responses = handle(request.parameters)
            for response in responses:
                self.__send_response(response)
        except AssuanError as err:
            self.__send_error_response(err)
        except Exception:
            log.error(
                'exception while executing %s:\n%s',
                handle,
                traceback.format_exc().rstrip(),
            )
            self.__send_error_response(
                AssuanError(message='Unspecific Assuan server fault')
            )
        return

    def __send_response(self, response: 'Response') -> None:
        """For internal use by ``._handle_requests()``."""
        # rstring = str(response)
        log.info('S: %s', response)
        if self.outtake:
            self.outtake.write(bytes(response))
            self.outtake.write(b'\n')
            try:
                self.outtake.flush()
            except IOError:
                if not self.stop:
                    raise
        else:
            raise Exception('no outtake message provided')

    def __send_error_response(self, error: AssuanError) -> None:
        """For internal use by ``._handle_requests()``."""
        self.__send_response(common.error_response(error))

    # common commands defined at
    # http://www.gnupg.org/documentation/manuals/assuan/Client-requests.html

    def _handle_bye(self, arg: str) -> Generator['Response', None, None]:
        if self.single_request:
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
            [<assuan.common.Response object at ...>]

            >>> s.options
            {'my-op': '1'}

            >>> list(s._handle_option('my-op 2'))  # doctest: +ELLIPSIS
            [<assuan.common.Response object at ...>]

            >>> s.options
            {'my-op': '2'}

            >>> list(s._handle_option('--my-op 3'))  # doctest: +ELLIPSIS
            [<assuan.common.Response object at ...>]

            >>> s.options
            {'my-op': '3'}

            >>> list(s._handle_option('my-op'))  # doctest: +ELLIPSIS
            [<assuan.common.Response object at ...>]

            >>> s.options
            {'my-op': None}

            >>> list(s._handle_option('inv'))
            Traceback (most recent call last):
              ...
            assuan.exception.AssuanError: 174 Unknown option

            >>> list(s._handle_option('in|valid'))
            Traceback (most recent call last):
              ...
            assuan.exception.AssuanError: 90 Invalid parameter
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
            log.info('skipping invalid option: %s', name)
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
        max_threads: int = 10,
        **kwargs: Any,
    ) -> None:
        """Initialize assuan IPC server."""
        self.name = name
        self.socket = socket
        self.server = server

        if 'close_on_disconnect' in kwargs:
            assert kwargs['close_on_disconnect'] == (
                True,
                kwargs['close_on_disconnect'],
            )
        else:
            kwargs['close_on_disconnect'] = True
        self.kwargs = kwargs
        self.max_threads = max_threads
        self.threads: List['Thread'] = []

    def run(self) -> None:
        """Run assuan socket server."""
        log.info('listen on socket')
        self.socket.listen()
        thread_index = 0
        while True:
            socket, address = self.socket.accept()
            log.info('connection from %s', address)
            self.__cleanup_threads()
            if len(self.threads) > self.max_threads:
                self.drop_connection(socket, address)
            self.__spawn_thread(
                f"server-thread-{thread_index}", socket, address
            )
            thread_index = (thread_index + 1) % self.max_threads

    def __cleanup_threads(self) -> None:
        i = 0
        while i < len(self.threads):
            thread = self.threads[i]
            thread.join(0)
            if thread.is_alive():
                log.info('joined thread %s', thread.name)
                self.threads.pop(i)
                thread.socket.shutdown()  # type: ignore
                thread.socket.close()  # type: ignore
            else:
                i += 1

    def drop_connection(self, socket: 'Socket', address: str) -> None:
        """Drop connection."""
        log.info('drop connection from %s', address)
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
