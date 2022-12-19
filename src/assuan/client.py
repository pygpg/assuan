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

"""PyAssuan client for interfacing with GPG Assuan."""

import logging
import socket as _socket
import sys
from types import TracebackType
from typing import TYPE_CHECKING, BinaryIO, Generator, List, Optional, Tuple

from assuan import common
from assuan.common import Request, Response
from assuan.exception import AssuanError

if TYPE_CHECKING:
    from socket import socket as Socket

log = logging.getLogger(__name__)


class AssuanClient:
    """A single-threaded Assuan client based on the `development suggestions`_.

    .. _development suggestions:

        http://www.gnupg.org/documentation/manuals/assuan/Client-code.html
    """

    def __init__(self, name: str, close_on_disconnect: bool = False) -> None:
        """Initialize assuan client."""
        self.name = name

        self.close_on_disconnect = close_on_disconnect
        self.socket: Optional['Socket'] = None
        self.intake: Optional[BinaryIO] = None
        self.outtake: Optional[BinaryIO] = None

    # def __enter__(self) -> 'AssuanClient':
    #     self.connection = open(

    def __exit__(
        self,
        exc_type: Optional[type[AssuanError]],
        exc_value: Optional[AssuanError],
        exc_traceback: TracebackType,
    ) -> None:
        ...

    def connect(self, socket_path: Optional[str] = None) -> None:
        """Connect."""
        if socket_path:
            log.info('connect to Unix socket at %s', socket_path)
            self.socket = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
            self.socket.connect(socket_path)
            self.intake = self.socket.makefile('rb')
            self.outtake = self.socket.makefile('wb')
        else:
            if not self.intake:
                log.info('read from stdin')
                self.intake = sys.stdin.buffer
            if not self.outtake:
                log.info('write to stdout')
                self.outtake = sys.stdout.buffer

    def disconnect(self) -> None:
        """Disconnect."""
        if self.close_on_disconnect:
            log.info('disconnecting')
            if self.intake is not None:
                self.intake.close()
                self.intake = None
            if self.outtake is not None:
                self.outtake.close()
                self.outtake = None
            if self.socket is not None:
                self.socket.shutdown(_socket.SHUT_RDWR)
                self.socket.close()
                self.socket = None

    # OPTIMIZE: log from error module instead
    # def raiseerror(self, error: AssuanError) -> None:
    #     """Raise error."""
    #     log.error(str(error))
    #     raise Exception(error)

    def read_response(self) -> 'Response':
        """Read response."""
        line = self.intake.readline() if self.intake else None
        if not line:
            raise AssuanError(message='IPC accept call failed')
        if len(line) > common.LINE_LENGTH:
            raise AssuanError(message='Line too long')
        if not line.endswith(b'\n'):
            log.info('S: %r', line)
            raise AssuanError(message='Invalid response')
        line = line.rstrip()  # remove trailing newline
        response = Response()
        try:
            response.from_bytes(line)
        except AssuanError as err:
            log.error(str(err))
            raise
        log.info('S: %s', response)
        return response

    def _write_request(self, request: 'Request') -> None:
        log.info('C: %s', request)
        if self.outtake is not None:
            self.outtake.write(bytes(request))
            self.outtake.write(b'\n')
            try:
                self.outtake.flush()
            except IOError:
                raise Exception('unable to flush outtake') from IOError
        else:
            raise Exception('no outtake provided')

    def make_request(
        self,
        request: 'Request',
        response: bool = True,
        expect: Optional[List[str]] = None,
    ) -> Optional[Tuple[List['Response'], Optional[bytes]]]:
        """Make request."""
        self._write_request(request=request)
        if response:
            return self.get_responses(
                requests=[request], expect=expect or ['OK']
            )
        return None

    def get_responses(
        self,
        requests: Optional[List['Request']] = None,
        expect: Optional[List[str]] = None,  # ['OK'],
    ) -> Tuple[List['Response'], Optional[bytes]]:
        """Get responses."""
        responses = list(self.responses)
        if responses and responses[-1].message == 'ERR':
            err_response = responses[-1]
            if err_response.parameters:
                fields = common.to_str(err_response.parameters).split(' ', 1)
                code = int(fields[0])
            else:
                fields = []
                code = 1
            if len(fields) > 1:
                message = fields[1].strip()
            else:
                message = None
            error = AssuanError(code=code, message=message)
            if requests is not None:
                setattr(error, 'requests', requests)
            setattr(error, 'responses', responses)
            raise error
        if expect and responses[-1].message not in expect:
            raise Exception('cannot find message in expect')
        rsps = []
        for response in responses:
            if response.message == 'D':
                if response.parameters:
                    rsps.append(common.to_bytes(response.parameters))
        data = b''.join(rsps) if rsps else None
        return (responses, data)

    @property
    def responses(self) -> Generator['Response', None, None]:
        """Iterate responses."""
        while True:
            response = self.read_response()
            yield response
            if response.message not in ['S', '#', 'D']:
                break

    def send_data(
        self,
        data: Optional[str] = None,
        response: bool = True,
        expect: Optional[List[str]] = None,
    ) -> Optional[Tuple[List['Response'], Optional[bytes]]]:
        """Iterate through requests necessary to send ``data`` to a server.

        http://www.gnupg.org/documentation/manuals/assuan/Client-requests.html
        """
        requests = []
        if data:
            encoded_data = common.encode(data)
            start = 0
            stop = min(
                common.LINE_LENGTH - 4, len(encoded_data)
            )  # 'D ', CR, CL
            log.debug('sending %s bytes of encoded data', len(encoded_data))
            while stop > start:
                # d = encoded_data[start:stop]
                request = Request(
                    command='D',
                    parameters=encoded_data[start:stop],
                    encoded=True,
                )
                requests.append(request)
                log.debug('send %s byte chunk', stop - start)
                self._write_request(request=request)
                start = stop
                stop = start + min(
                    common.LINE_LENGTH - 4, len(encoded_data) - start
                )
        request = Request('END')
        requests.append(request)
        self._write_request(request=request)
        if response:
            return self.get_responses(
                requests=requests, expect=expect or ['OK']
            )
        return None

    def send_fds(self, fds: List[int]) -> int:
        """Send file descriptors over a Unix socket."""
        if self.socket:
            _msg = f"# descriptors in flight: {fds}\n"
            log.info('C: %s', _msg.rstrip('\n'))
            msg = _msg.encode('utf-8')
            return common.send_fds(socket=self.socket, msg=msg, fds=fds)
        raise AssuanError(code=279, message='No output source for IPC')

    def recieve_fds(self, msglen: int = 200, maxfds: int = 10) -> List[int]:
        """Receive file descriptors over a Unix socket."""
        if self.socket:
            msg, fds = common.receive_fds(
                socket=self.socket,
                msglen=msglen,
                maxfds=maxfds,
            )
            string = msg.decode('utf-8')
            log.info('S: %s', string.rstrip('\n'))
            return fds
        raise AssuanError(code=278, message='No input source for IPC')
