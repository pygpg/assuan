#!/usr/bin/env python3
#
# Copyright (C) 2012-2017 W. Trevor King <wking@tremily.us>
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

"""Simple pinentry program for getting pins from a terminal."""

import copy
import logging
import os
import re
import signal
import sys
import termios
from typing import Any, Dict, Generator

from assuan import __version__
from assuan.common import Response
from assuan.exception import AssuanError
from assuan.server import AssuanServer

log = logging.getLogger(__name__)
log.setLevel(logging.ERROR)
log.addHandler(logging.StreamHandler())
log.addHandler(logging.FileHandler('/tmp/pinentry.log'))
# log.addHandler(logging_handlers.SysLogHandler(address='/dev/log'))


class PinEntry(AssuanServer):
    """Represent a pinentry protocol server.

    See ``pinentry-0.8.0/doc/pinentry.texi`` at::

        ftp://ftp.gnupg.org/gcrypt/pinentry/
        http://www.gnupg.org/aegypten/

    for details on the pinentry interface.

    Alternatively, you can just watch the logs and guess ;).  Here's a
    trace when driven by GnuPG 2.0.28 (libgcrypt 1.6.3)::

        S: OK Your orders please
        C: OPTION grab
        S: OK
        C: OPTION ttyname=/dev/pts/6
        S: OK
        C: OPTION ttytype=xterm
        S: OK
        C: OPTION lc-ctype=en_US.UTF-8
        S: OK
        C: OPTION lc-messages=en_US.UTF-8
        S: OK
        C: OPTION allow-external-password-cache
        S: OK
        C: OPTION default-ok=_OK
        S: OK
        C: OPTION default-cancel=_Cancel
        S: OK
        C: OPTION default-yes=_Yes
        S: OK
        C: OPTION default-no=_No
        S: OK
        C: OPTION default-prompt=PIN:
        S: OK
        C: OPTION default-pwmngr=_Save in password manager
        S: OK
        C: OPTION default-cf-visi=Do you really want to make your passphrase
            visible on the screen?
        S: OK
        C: OPTION default-tt-visi=Make passphrase visible
        S: OK
        C: OPTION default-tt-hide=Hide passphrase
        S: OK
        C: GETINFO pid
        S: D 14309
        S: OK
        C: SETKEYINFO u/S9464F2C2825D2FE3
        S: OK
        C: SETDESC Enter passphrase%0A
        S: OK
        C: SETPROMPT Passphrase
        S: OK
        C: GETPIN
        S: D testing!
        S: OK
        C: BYE
        S: OK closing connection
    """

    _digitregexp = re.compile(r'\d+')

    # from proc(5): pid comm state ppid pgrp session tty_nr tpgid
    _tpgrpregexp = re.compile(r'\d+ \(\S+\) . \d+ \d+ \d+ \d+ (\d+)')

    def __init__(
        self,
        name: str = 'pinentry',
        strict_options: bool = False,
        single_request: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize pinentry object."""
        self.strings: Dict[str, Any] = {}
        self.connection: Dict[str, Any] = {}
        super().__init__(
            name=name,
            strict_options=strict_options,
            single_request=single_request,
            **kwargs,
        )
        self.valid_options.append('ttyname')

    def reset(self) -> None:
        """Reset connection."""
        super().reset()
        self.strings.clear()
        self.connection.clear()

    # user interface

    def _connect(self) -> None:
        log.info('connecting to user')
        log.debug("options:\n%s", self.options)
        tty_name = self.options.get('ttyname', None)
        if tty_name:
            self.connection['tpgrp'] = self._get_pgrp(tty_name)
            log.info("open to-user output stream for %s", tty_name)
            self.connection['to_user'] = open(tty_name, 'w', encoding='utf-8')
            log.info("open from-user input stream for %s", tty_name)
            self.connection['from_user'] = open(
                tty_name, 'r', encoding='utf-8'
            )
            log.info('get current termios line discipline')
            self.connection['original termios'] = termios.tcgetattr(
                self.connection['to_user']
            )  # [iflag, oflag, cflag, lflag, ...]
            newtermios = copy.deepcopy(self.connection['original termios'])
            # translate carriage return to newline on input
            newtermios[0] |= termios.ICRNL
            # do not ignore carriage return on input
            newtermios[0] &= ~termios.IGNCR
            # do not echo input characters
            newtermios[3] &= ~termios.ECHO
            # echo input characters
            # newtermios[3] |= termios.ECHO
            # echo the NL character even if ECHO is not set
            newtermios[3] |= termios.ECHONL
            # enable canonical mode
            newtermios[3] |= termios.ICANON
            log.info('adjust termios line discipline')
            termios.tcsetattr(
                self.connection['to_user'], termios.TCSANOW, newtermios
            )
            log.info("send SIGSTOP to pgrp %s", self.connection['tpgrp'])
            # os.killpg(self.connection['tpgrp'], signal.SIGSTOP)
            os.kill(self.connection['tpgrp'], signal.SIGSTOP)
            self.connection['tpgrp stopped'] = True
        else:
            log.info('no TTY name given; use stdin/stdout for I/O')
            self.connection['to_user'] = sys.stdout
            self.connection['from_user'] = sys.stdin
        log.info('connected to user')
        # give a clean line to work on
        self.connection['to_user'].write(os.linesep)
        self.connection['active'] = True

    def _disconnect(self) -> None:
        log.info('disconnecting from user')
        try:
            if self.connection.get('original termios', None):
                log.info('restore original termios line discipline')
                termios.tcsetattr(
                    self.connection['to_user'],
                    termios.TCSANOW,
                    self.connection['original termios'],
                )
            if self.connection.get('tpgrp stopped', None) is True:
                log.info('send SIGCONT to pgrp %s', self.connection['tpgrp'])
                # os.killpg(self.connection['tpgrp'], signal.SIGCONT)
                os.kill(-self.connection['tpgrp'], signal.SIGCONT)
            if self.connection.get('to_user', None) not in [None, sys.stdout]:
                log.info('close to-user output stream')
                self.connection['to_user'].close()
            if self.connection.get('from_user', None) not in [
                None,
                sys.stdout,
            ]:
                log.info('close from-user input stream')
                self.connection['from_user'].close()
        finally:
            self.connection = {'active': False}
            log.info('disconnected from user')

    def _get_pgrp(self, tty_name: str) -> int:
        log.info("find process group contolling %s", tty_name)
        proc = '/proc'
        for name in os.listdir(proc):
            path = os.path.join(proc, name)
            if not (self._digitregexp.match(name) and os.path.isdir(path)):
                continue  # not a process directory
            log.debug("checking process %s", name)
            fd_path = os.path.join(path, 'fd', '0')
            try:
                link = os.readlink(fd_path)
            except OSError as err:
                log.debug("not our process: %s", err)
                continue  # permission denied (not one of our processes)
            if link != tty_name:
                log.debug("wrong tty: %s", link)
                continue  # not attached to our target tty
            stat_path = os.path.join(path, 'stat')
            stat = open(stat_path, 'r', encoding='utf-8').read()
            log.debug("check stat for pgrp: %s", stat)
            match = self._tpgrpregexp.match(stat)
            if match is not None:
                pgrp = int(match.group(1))
                log.info("found pgrp %s for %s", pgrp, tty_name)
                return pgrp
            raise Exception('no match found')
        raise ValueError(tty_name)

    def _write(self, string: str) -> None:
        """Write text to the user's terminal."""
        self.connection['to_user'].write(string + '\n')
        self.connection['to_user'].flush()

    def read(self):
        """Read and return a line from the user's terminal."""
        # drop trailing newline
        return self.connection['from_user'].readline()[:-1]

    def _prompt(self, prompt: str = '?', error=None, add_colon: bool = True):
        if add_colon:
            prompt += ':'
        if error:
            self.connection['to_user'].write(error)
            self.connection['to_user'].write('\n')
        self.connection['to_user'].write(prompt)
        self.connection['to_user'].write(' ')
        self.connection['to_user'].flush()
        return self.read()

    # assuan handlers

    @staticmethod
    def _handle_getinfo(arg: str) -> Generator['Response', None, None]:
        if arg == 'pid':
            yield Response('D', str(os.getpid()).encode('utf-8'))
        elif arg == 'version':
            yield Response('D', __version__.encode('utf-8'))
        else:
            raise AssuanError(message='Invalid parameter')
        yield Response('OK')

    def _handle_setkeyinfo(self, arg: str):
        self.strings['key info'] = arg
        yield Response('OK')

    @staticmethod
    def _handle_clearpassphrase(arg: str) -> Generator[Response, None, None]:
        yield Response('OK')

    def _handle_setdesc(self, arg: str) -> Generator[Response, None, None]:
        self.strings['description'] = arg
        yield Response('OK')

    def _handle_setprompt(self, arg: str) -> Generator[Response, None, None]:
        self.strings['prompt'] = arg
        yield Response('OK')

    def _handle_seterror(self, arg: str) -> Generator[Response, None, None]:
        self.strings['error'] = arg
        yield Response('OK')

    def _handle_settitle(self, arg: str) -> Generator[Response, None, None]:
        self.strings['title'] = arg
        yield Response('OK')

    def _handle_setok(self, arg: str) -> Generator[Response, None, None]:
        self.strings['ok'] = arg
        yield Response('OK')

    def _handle_setcancel(self, arg: str) -> Generator[Response, None, None]:
        self.strings['cancel'] = arg
        yield Response('OK')

    def _handle_setnotok(self, arg: str) -> Generator[Response, None, None]:
        self.strings['not ok'] = arg
        yield Response('OK')

    def _handle_setqualitybar(
        self, arg: str
    ) -> Generator[Response, None, None]:
        """Add a quality indicator to the GETPIN window.

        This indicator is updated as the passphrase is typed.  The
        clients needs to implement an inquiry named "QUALITY" which
        gets passed the current passphrase (percent-plus escaped) and
        should send back a string with a single numerical vauelue
        between -100 and 100.  Negative values will be displayed in
        red.

        If a custom label for the quality bar is required, just add
        that label as an argument as percent escaped string.  You will
        need this feature to translate the label because pinentry has
        no internal gettext except for stock strings from the toolkit
        library.

        If you want to show a tooltip for the quality bar, you may use

            C: SETQUALITYBAR_TT string
            S: OK

        With STRING being a percent escaped string shown as the tooltip.

        Here is a real world example of these commands in use:

            C: SETQUALITYBAR Quality%3a
            S: OK
            C: SETQUALITYBAR_TT The quality of the text entered above.%0a\
            Please ask your administrator for details about the criteria.
            S: OK
        """
        self.strings['qualitybar'] = arg
        yield Response('OK')

    def _handle_setqualitybar_tt(
        self, arg: str
    ) -> Generator[Response, None, None]:
        self.strings['qualitybar_tooltip'] = arg
        yield Response('OK')

    def _handle_getpin(self, arg: str) -> Generator[Response, None, None]:
        try:
            self._connect()
            self._write(self.strings['description'])
            if 'key info' in self.strings:
                self._write(f"key: {self.strings['key info']}")
            if 'qualitybar' in self.strings:
                self._write(self.strings['qualitybar'])
            pin = self._prompt(
                prompt=self.strings['prompt'],
                error=self.strings.get('error'),
                add_colon=False,
            )
        finally:
            self._disconnect()
        yield Response('D', pin.encode('utf-8'))
        yield Response('OK')

    def _handle_confirm(self, arg: str) -> Generator[Response, None, None]:
        try:
            self._connect()
            self._write(self.strings['description'])
            self._write('1) ' + self.strings['ok'])
            self._write('2) ' + self.strings['not ok'])
            value = self._prompt('?')
        finally:
            self._disconnect()
        if value == '1':
            yield Response('OK')
        raise AssuanError(message='Not confirmed')

    def _handle_message(self, arg: str) -> Generator[Response, None, None]:
        self._write(self.strings['description'])
        yield Response('OK')

    # def _handle_confirm(self, args: str) -> Generator[Response, None, None]:
    #     assert args == '--one-button', args
    #     try:
    #         self._connect()
    #         self._write(self.strings['description'])
    #         self._write('1) ' + self.strings['ok'])
    #         value = self._prompt('?')
    #     finally:
    #         self._disconnect()
    #     assert value == '1', value
    #     yield Response('OK')


if __name__ == '__main__':
    import argparse
    import traceback

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-v',
        '--version',
        action='version',
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        '-V', '--verbose', action='count', default=0, help='increase verbosity'
    )
    parser.add_argument(
        '--display', help='set X display (ignored by this implementation)'
    )

    args = parser.parse_args()

    p = PinEntry()

    if args.verbose:
        log.setLevel(max(logging.DEBUG, log.level - 10 * args.verbose))

    try:
        p.run()
    except Exception:
        log.error(
            "exiting due to exception:\n%s", traceback.format_exc().rstrip()
        )
        raise
