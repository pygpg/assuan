Python module and tools for communicating in the Assuan_ protocol.

There are a number of GnuPG_ wrappers for python `out there`__, but
they mostly work via the ``gpg`` executable.  This is an attempt to
cut to the chase and speak directly to ``gpgme-tool`` (source__) over
a well-defined socket protocol.

__ wrappers_
__ gpgme-tool_

Installation
============

Dependencies
------------

``assuan`` is a simple package with no external dependencies outside
the Python 3.6+ standard library.

Contributing
------------

``assuan`` is available as a Git_ repository::

  $ git clone https://github.com/pygpg/assuan.git

See the homepage_ for details.  To install the checkout, run the
standard::

  $ pip install -e .[dev]

Usage
=====

Checkout the docstrings and the examples in ``bin``.

Testing
=======

Run the internal unit tests with pytest::

  $ python -m pytest

To test running servers by hand, you can use `gpg-connect-agent`_.
Despite the name, this program can connect to any Assuan server::

  $ gpg-connect-agent --raw-socket name

Licence
=======

This project is distributed under the `GNU General Public License
Version 3`_ or greater.

Author
======

Jesse P. Johnson <jpj6652@gmail.com>
W. Trevor King <wking@tremily.us>

References
==========

.. _Assuan: http://www.gnupg.org/documentation/manuals/assuan/
.. _GnuPG: http://www.gnupg.org/
.. _wrappers: http://wiki.python.org/moin/GnuPrivacyGuard
.. _gpgme-tool:
  http://git.gnupg.org/cgi-bin/gitweb.cgi?p=gpgme.git;a=blob;f=src/gpgme-tool.c;hb=HEAD
.. _Git: http://git-scm.com/
.. _homepage: http://blog.tremily.us/posts/pyassuan/
.. _gpg-connect-agent:
  http://www.gnupg.org/documentation/manuals/gnupg-devel/gpg_002dconnect_002dagent.html
.. _GNU General Public License Version 3: http://www.gnu.org/licenses/gpl.html
