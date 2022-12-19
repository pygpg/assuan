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

"""A Python implementation of the `Assuan protocol`_.

.. _Assuan protocol: http://www.gnupg.org/documentation/manuals/assuan/
"""

import logging
from typing import List

from assuan.client import AssuanClient  # noqa
from assuan.exception import AssuanError  # noqa
from assuan.common import Request, Response, error_response  # noqa
from assuan.server import AssuanServer, AssuanSocketServer  # noqa

__author__ = 'Jesse P. Johnson'
__author_email__ = 'jpj6652@gmail.com'
__title__ = 'assuan'
__description__ = 'A Python implementation of the `Assuan protocol.'
__version__ = '0.2.1b1'
__license__ = 'GPL-3.0'
__all__: List[str] = [
    'AssuanClient',
    'AssuanError',
    'AssuanServer',
    'AssuanSocketServer',
    'Request',
    'Response',
    'error_response',
]

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

# log.setLevel(logging.ERROR)
# log.addHandler(logging.StreamHandler())
# log.addHandler(logging.FileHandler('/tmp/pinentry.log'))
# log.addHandler(logging_handlers.SysLogHandler(address='/dev/log'))
# log.handlers[0].setFormatter(
#     logging.Formatter('%(name)s: %(levelname)s: %(message)s')
# )
