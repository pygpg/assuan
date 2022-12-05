Python module and tools for communicating in the Assuan_ protocol.

There are a number of GnuPG_ wrappers for python `out there`__, but
they mostly work via the ``gpg`` executable.  This is an attempt to
cut to the chase and speak directly to ``gpgme-tool`` (source__) over
a well-defined socket protocol.

__ wrappers_
__ gpgme-tool_

Installation
============

Packages
--------

Gentoo
~~~~~~

I've packaged ``pyassuan`` for Gentoo_.  You need layman_ and
my `wtk overlay`_.  Install with::

  # emerge -av app-portage/layman
  # layman --add wtk
  # emerge -av dev-python/pyassuan


Dependencies
------------

``pyassuan`` is a simple package with no external dependencies outside
the Python 3.6+ standard library.


Contributing
------------

``pyassuan`` is available as a Git_ repository::

  $ git clone https://github.com/pygpg.git
  $ pip install -e .[dev]
See the homepage_ for details.  To install the checkout, run the
standard::

  $ python setup.py install

Usage
=====

Checkout the docstrings and the examples in ``bin``.

Testing
=======

Run the internal unit tests with `Python 3.2+'s unittest discovery`__::

  $ python -m nose2

To test running servers by hand, you can use `gpg-connect-agent`_.
Despite the name, this program can connect to any Assuan server::

  $ gpg-connect-agent --raw-socket name

__ unittest-discovery_

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
.. _Gentoo: http://www.gentoo.org/
.. _layman: http://layman.sourceforge.net/
.. _wtk overlay: http://blog.tremily.us/posts/Gentoo_overlay/
.. _Git: http://git-scm.com/
.. _homepage: http://blog.tremily.us/posts/pyassuan/
.. _gpg-connect-agent:
  http://www.gnupg.org/documentation/manuals/gnupg-devel/gpg_002dconnect_002dagent.html
.. _unittest-discovery:
  https://docs.python.org/3.5/library/unittest.html#unittest-test-discovery
.. _GNU General Public License Version 3: http://www.gnu.org/licenses/gpl.html
