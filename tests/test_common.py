# Copyright (C) 2012-2018 W. Trevor King <wking@tremily.us>
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
# type: ignore

"""Test common assuan methods."""

from assuan import common


def testencode():
    """Test encode of special characters."""
    assert common.encode('It grew by 5%!\n') == 'It grew by 5%25!%0A'
    assert common.encode(b'It grew by 5%!\n') == b'It grew by 5%25!%0A'


def testdecode():
    """Test decode of special characters."""
    assert common.decode('%22Look out!%22%0AWhere%3F') == '"Look out!"\nWhere?'
    assert (
        common.decode(b'%22Look out!%22%0AWhere%3F') == b'"Look out!"\nWhere?'
    )


def testfrom_hex():
    """Test hex to string conversion."""
    assert common.from_hex('%22') == '"'
    assert common.from_hex('%0A') == '\n'
    assert common.from_hex(b'%0A') == b'\n'


def testto_hex():
    """Test string to hex conversion."""
    assert common.to_hex('"') == '%22'
    assert common.to_hex('\n') == '%0A'
    assert common.to_hex(b'\n') == b'%0A'


def testto_str():
    """Test string conversion from bytes."""
    assert isinstance(common.to_str(b'A byte string'), str)
    assert isinstance(common.to_str('A string'), str)


def testto_bytes():
    """Test byte conversion to string."""
    assert isinstance(common.to_bytes(b'A byte string'), bytes)
    assert isinstance(common.to_bytes('A string'), bytes)
