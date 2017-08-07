fdict
=====

|PyPI-Status| |PyPI-Versions|

|Build-Status| |Branch-Coverage-Status| |Codacy-Grade|

|LICENCE|


Easy out-of-core computing with recursive data structures in Python with a drop-in dict replacement. Just use ``sfdict()`` instead of ``dict()``, you are good to go!

``fdict`` and ``sfdict`` can be initialized with a standard ``dict``:

.. code:: python

    from fdict import fdict, sfdict
    d = fdict({'a': {'b': 1, 'c': [2, 3]}, 'd': 4})

``Out: {'a/c': [2, 3], 'd': 4, 'a/b': 1}``

Nested dicts will be converted on-the-fly:

.. code:: python

    d['e'] = {'f': {'g': {'h': 5}}}

``Out: {'e/f/g/h': 5, 'a/c': [2, 3], 'd': 4, 'a/b': 1}``

And it can be converted back to a dict at any time:

.. code:: python

    d.to_dict_nested()

``Out: {'a': {'c': [2, 3], 'b': 1}, 'e': {'f': {'g': {'h': 5}}}, 'd': 4}``

To store all items on disk (out-of-core computing), use ``sfdict``, a subclass of ``fdict`` using ``shelve`` internally:

.. code:: python

    # Initialize an empty database in file myshelf.db
    d = sfdict(filename='myshelf.db')
    d['a'] = {'b': 1, 'c': [2, 3]}
    d.sync()  # synchronize all changes back to disk
    d.close()  # should always close a db

    # Reopen the same database
    d2 = sfdict(filename='myshelf.db')
    print(d2)
    d2.close()

``Out: {'a/b': 1, 'a/c': [2, 3]}``

The intention of this module is to provide a very easy and pythonic data structure to do out-of-core computing of very nested/recursive big data, while still having reasonably acceptable performances. Currently, no other library can do out-of-core computing of very recursive data, because they all serialize at 1st level nodes. Hence, the goal is to provide a very easy way to prototype out-of-core applications, which you can later replace with a faster datatype.

Hence, this module provides ``fdict()`` and ``sfdict()``, which both provide a similar interface to ``dict()`` with flattened keys for the first and out-of-core storage for the second (using native ``shelve`` library). There is no third-party dependancy.

The ``fdict()`` class provides the basic system allowing to have an internal flattened representation of a nested dict, then you can subclass it to support your favorite out-of-core library as long as it implements dict-like methods: an exemple is provided with ``sfdict()`` using ``shelve``, but you can subclass to use ``chest``, ``shove``, ``sqlite``, ``zodb``, etc.

Note: if you use ``sfdict()``, do not forget to ``.sync()`` and ``.close()`` to commit the changes back to the file.

An alternative based on numpy can be found in the `wendelin.core project <https://github.com/Nexedi/wendelin.core>`__, and there is also dask for pandas dataframes.

Differences with dict
----------------------------

Although maximum compatibility was the primary goal, a different implementation of course brings differences that are unavoidable.

The primary difference is that calling `items()`, `keys()`, `values()` and `view*` methods will return all children leaves nested at any level, whereas a dict returns only the direct children. Also, by default, these methods return only leaves (non-dict objects) and not nodes, although you can override this by suppling the `nodes=True` argument.

Another difference is conflicts: you can have an item being both a leaf and a node, because there is no way to check that there is no node without walking all items (ie, using ``viewitems()``, and this method is the limitation of ``fdict`` data structure).

This also means that when assigning an item that was already assigned, nodes will NOT get replaced, but singleton will be correctly replaced. To be more explicit:

This works:

.. code:: python

    d = fdict({'a': 1, 'b': {'c': 2}})
    d['a'] = -1
    print(d)
    d['a'] = {'d': 3, 'e': 4}
    print(d)

``{'a': -1, 'b/c': 2}``
``{'a/d': 3, 'a/e': 4, 'b/c': 2}``

But this does NOT work as expected:

.. code:: python

    d = fdict({'a': 1, 'b': {'c': 2}})
    d['b'] = -1
    print(d)

``{'a': 1, 'b': -1, 'b/c': 2}``

Performances
--------------------

``fdict`` was made with maximum compatibility with existing code using ``dict`` and with reasonable performances. That's in theory, in practice ``fdict`` are slower than ``dict`` for most purposes, except setitem and getitem if you use direct access form (eg, x['a/b/c'] instead of x['a']['b']['c']).

As such, you can expect O(1) performance just like ``dict`` for any operation on leaves (non-dict objects): getitem, setitem, delitem, eq contains. In practice, ``fdict`` is about 10x slower than ``dict`` because of class overhead and key string manipulation, for both indirect access (ie, ``x['a']['b']['c']``) and 3x slower for direct access on leaves (ie, ``x['a/b/c']``). Thus direct access form might be preferable if you want a faster set and get. This performance cost is acceptable for a quick prototype of a bigdata database, since building and retrieving items are the most common operations.

The major drawback comes when you work on nodes (nested dict objects): since all keys are flattened and on the same level, the only way to get only the children of a nested dict (aka a branch) is to walk through all keys and filter out the ones not matching the current branch. This means that any operation on nodes will be in O(n) where n is the total number of items in the whole fdict. Affected operations are: items, keys, values, view*, iter*, delitem on nodes, eq on nodes, contains on nodes.

Interestingly, getitem on nodes is not affected, because we use a lazy approach: getting a nested dict will not build anything, it will just spawn a new fdict with a different filtering rootpath. Nothing gets evaluated, until you either attain a leaf (in this case we return the non-dict object value) or you use an operation on node such as items(). Keep in mind that any nested fdict will share the same internal flattened dict, so any nested fdict will also have access to all items at any level!

This was done by design: ``fdict`` is made to be as fast as ``dict`` to build and to retrieve leaves, in exchange for slower exploration. In other words, you can expect blazingly fast creation of ``fdict`` as well as getting any leaf object at any nested level, but you should be careful when exploring. However, even if your dict is bigger than RAM, you can use the view* methods (viewitems, viewkeys, viewvalues) to walk all the items as a generator.

To circumvent this pitfall, two things were implemented:

    * ``extract()`` method can be used on a nested fdict to filter all keys once and build a new fdict containing only the pertinent nested items. Usage is ``extracted_fdict = fdict({'a': {'b': 1, 'c': [2, 3]}})['a'].extract()``.

    * ``fastview=True`` argument can be used when creating a fdict to enable the FastView mode. This mode will imply a small memory/space overhead to store nodes and also will increase complexity of setitem on nodes to O(m*l) where m is the number of parents of the current leaf added, and l the number of leaves added (usually one but if you set a dict it will be converted to multiple leaves). On the other hand, it will make items, keys, values, view* and other nodes operations methods as fast as with a ``dict`` by using lookup tables to access direct children directly, which was O(n) where n was the whole list of items at any level in the fdict. It is possible to convert a non-fastview fdict to a fastview fdict, just by supplying it as the initialization dict.

Thus, if you want to do data exploration on a ``fdict``, you can use either of these two approaches to speed up your exploration to a reasonable time, with performances close to a ``dict``. In practice, ``extract`` is better if you have lots of items per nesting level, whereas ``fastview`` might be better if you have a very nested structure with few items per level but lots of levels.

There is probably room for speed optimization, if you have any idea please feel free to open an issue on Github.

In any case, this module is primarily meant to do quick prototypes of bigdata databases, that you can then switch to another faster database after reworking the structure a bit.

A good example is the retrieval of online data: in this case, you care less about the data structure performance since it is negligible compared to network bandwidth and I/O. Then, when you have the data, you can rework it to convert to another type of database with a flat schema (by extracting only the fields you are interested in).

Also you can convert a ``fdict`` or ``sfdict`` to a flat ``dict`` using the ``to_dict()`` method, or to a nested (natural) ``dict`` using ``to_dict_nested()``, you will then get a standard ``dict`` stored in RAM that you can access at full speed, or use as an input to initialize another type of out-of-core database.

LICENCE
-------------

This library is licensed under MIT License.
Included are the ``flatkeys`` function by `bfontaine <https://github.com/bfontaine/flatkeys>`__  and ``_count_iter_items`` by `zuo <https://stackoverflow.com/a/15112059/1121352>`__.


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