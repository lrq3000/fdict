fdict
====

|PyPI-Status| |PyPI-Versions|

|Build-Status| |Branch-Coverage-Status| |Codacy-Grade|

|LICENCE|


Easy out-of-core computing with recursive data structures in Python with a drop-in dict replacement. Just use ``sfdict()`` instead of ``dict()``, you are good to go!

The intention of this module is to provide a very easy and pythonic data structure to do out-of-core computing of very recursive big data, while still giving sensibly good performances. Currently, no other library can do out-of-core computing of very recursive data, because they all serialize at 1st level nodes.

Hence, this module provides ``fdict()`` and ``sfdict()``, which both provide a similar interface to ``dict()`` with flattened keys for the first and out-of-core storage for the second (using native ``shelve`` library). There is no third-party dependancy.

The ``fdict()`` class provides the basic system allowing to have an internal flattened representation of a nested dict, then you can subclass it to support your favorite out-of-core library as long as it implements dict-like methods: an exemple is provided with ``sfdict()`` using ``shelve``, but you can subclass to use ``chest``, ``shove``, ``sqlite``, ``zodb``, etc.

An alternative based on numpy can be found in the `wendelin.core project <https://github.com/Nexedi/wendelin.core>`__.


.. |Build-Status| image:: https://travis-ci.org/lrq3000/fdict.svg?branch=master
   :target: https://travis-ci.org/lrq3000/fdict
.. |LICENCE| image:: https://img.shields.io/pypi/l/fdict.svg
   :target: https://raw.githubusercontent.com/lrq3000/fdict/master/LICENCE
.. |PyPI-Status| image:: https://img.shields.io/pypi/v/fdict.svg
   :target: https://pypi.python.org/pypi/fdict
.. |PyPI-Downloads| image:: https://img.shields.io/pypi/dm/fdict.svg
   :target: https://pypi.python.org/pypi/fdict
.. |PyPI-Versions| image:: https://img.shields.io/pypi/pyversions/fdict.svg
   :target: https://pypi.python.org/pypi/fdict
.. |Branch-Coverage-Status| image:: https://codecov.io/github/lrq3000/fdict/coverage.svg?branch=master
   :target: https://codecov.io/github/lrq3000/fdict?branch=master
.. |Codacy-Grade| image:: https://api.codacy.com/project/badge/Grade/3f965571598f44549c7818f29cdcf177
   :target: https://www.codacy.com/app/lrq3000/fdict?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=lrq3000/fdict&amp;utm_campaign=Badge_Grade