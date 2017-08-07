#!/usr/bin/env python
#
# fdict
# Copyright (C) 2017 Larroque Stephen
#
# Licensed under the MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import collections
import itertools
import os
import shelve
import sys
import tempfile

from pickle import HIGHEST_PROTOCOL as PICKLE_HIGHEST_PROTOCOL
from types import GeneratorType


PY3 = (sys.version_info >= (3,0))

if PY3:  # pragma: no cover
    _zip = zip
else:
    _zip = itertools.izip


__all__ = ['fdict', 'sfdict']


class fdict(dict):
    '''
    Flattened nested dict, all items are settable and gettable through ['item1']['item2'] standard form or ['item1/item2'] internal form.
    This allows to replace the internal dict with any on-disk storage system like a shelve's shelf (great for huge nested dicts that cannot fit into memory).
    Main limitation: an entry can be both a singleton and a nested fdict: when an item is a singleton, you can setitem to replace to a nested dict, but if it is a nested dict and you setitem it to a singleton, both will coexist. Except for fastview mode, there is no way to know if a nested dict exists unless you walk through all items, which would be too consuming for a simple setitem. In this case, a getitem will always return the singleton, but nested leaves can always be accessed via items() or by direct access (eg, x['a/b/c']).

    Fastview mode: remove conflicts issue and allow for fast O(m) contains(), delete() and view*() (such as vieitems()) where m in the number of subitems, instead of O(n) where n was the total number of elements in the fdict(). Downside is setitem() being O(m) too because of nodes metadata building, and memory/storage overhead, since we store all nodes and leaves lists in order to allow for fast lookup.
    '''
    def __init__(self, d=None, rootpath='', delimiter='/', fastview=False, nodel=False, **kwargs):
        '''
        Parameters
        ----------
        d  : dict, optional
            Initialize with a pre-existing dict.
            Also used internally to pass a reference to parent fdict.
        rootpath : str, optional
            Internal variable, define the nested level.
        delimiter  : str, optional
            Internal delimiter for nested levels. Can also be used for
            getitem direct access (e.g. ``x['a/b/c']``).
            [default : '/']
        fastview  : bool, optional
            Activates fastview mode, which makes setitem slower
            in O(m*l) instead of O(1), but makes view* methods
            (viewitem, viewkeys, viewvalues) as fast as dict's.
            [default : False]
        nodel  : bool, optional
            Activates nodel mode, which makes contains test
            in O(1) for nodes (leaf test is always O(1) in any mode).
            Only drawback: delitem is not suppressed.
            Useful for quick building of databases, then you can
            reopen the database with a normal fdict if you want
            the ability to delitem.
            [default : False]
        Returns
        -------
        out  : dict-like object.
        '''
        # Init self parameters
        self.rootpath = rootpath
        self.delimiter = delimiter
        self.fastview = fastview
        self.nodel = nodel
        self.kwargs = kwargs  # store all kwargs for easy subclassing

        if d is not None:
            if rootpath:
                # Internal call, we get a subdict, we just create a new fdict with the same dictionary but with a restricted rootpath
                if isinstance(d, dict):
                    self.d = d
                elif isinstance(d, (list, GeneratorType)):
                    # sometimes (particularly extract(fullpath=True)) we get a list of tuples instead of a dict
                    self.d = dict(d)
                else:
                    # if we use a shelve or probably other types of out-of-core dicts, we will get an object that is not a subclass of dict, so we should just trust the sender and keep the supplied dict as-is
                    self.d = d
            elif isinstance(d, self.__class__):
                # We were supplied a fdict, initialize a copy
                self.d = d.copy().d
            else: 
                # Else it is not an internal call, the user supplied a dict to initialize the fdict, we have to flatten its keys
                if not isinstance(d, dict):
                    # User supplied another type of object than dict, we try to convert to a dict and flatten it
                    d = dict(d)
                self.d = self.flatkeys(d, sep=delimiter)
                if fastview:
                    self._build_metadata()
                elif nodel:
                    self._build_metadata_nodel()
        else:
            # No dict supplied, create an empty dict
            self.d = dict()

        # Call compatibility layer
        self._viewkeys, self._viewvalues, self._viewitems = self._getitermethods(self.d)

    @staticmethod
    def _getitermethods(d):
        '''Defines what function to use to access the internal dictionary items most efficiently depending on Python version'''
        if PY3:  # pragma: no cover
            # Py3
            _viewkeys = d.keys
            _viewvalues = d.values
            _viewitems = d.items
        else:
            # Py2
            if getattr(d, 'viewvalues', None):
                # Py2.7
                _viewkeys = d.viewkeys
                _viewvalues = d.viewvalues
                _viewitems = d.viewitems
            else:
                # Py2.6
                _viewkeys = d.iterkeys
                _viewvalues = d.itervalues
                _viewitems = d.iteritems
        return _viewkeys, _viewvalues, _viewitems

    def _generickeys(self, d, **kwargs):
        return self._getitermethods(d)[0](**kwargs)

    def _genericitems(self, d, **kwargs):
        return self._getitermethods(d)[2](**kwargs)

    @staticmethod
    def _get_all_parent_nodes(path, delimiter='/'):
        '''Get path to all parent nodes for current leaf, starting from leaf's direct parent down to root'''
        pos = path.rfind(delimiter)
        while pos != -1:
            yield path[:pos+1]
            pos = path.rfind(delimiter, 0, pos)

    @staticmethod
    def _get_all_parent_nodes_nested(path, delimiter='/'):
        '''Get path to all parent nodes for current leaf, starting from root down to leaf's direct parent, and return only the relative key (not the fullkey)'''
        pos = path.find(delimiter)
        lastpos = 0
        while pos != -1:
            yield path[lastpos:pos]
            lastpos = pos+1
            pos = path.find(delimiter, pos+1)

    @staticmethod
    def _get_parent_node(path, delimiter='/'):
        '''Get path to the first parent of current leaf'''
        endpos = len(path)  # 'a/b' (leaf)
        if path.endswith(delimiter):  # 'a/b/' (node)
            endpos -= 1
        return path[:path.rfind(delimiter, 0, endpos)+1]

    @staticmethod
    def flatkeys(d, sep="/"):
        """
        Flatten a dictionary: build a new dictionary from a given one where all
        non-dict values are left untouched but nested ``dict``s are recursively
        merged in the new one with their keys prefixed by their parent key.

        >>> flatkeys({1: 42, 'foo': 12})
        {1: 42, 'foo': 12}
        >>> flatkeys({1: 42, 'foo': 12, 'bar': {'qux': True}})
        {1: 42, 'foo': 12, 'bar.qux': True}
        >>> flatkeys({1: {2: {3: 4}}})
        {'1.2.3': 4}
        >>> flatkeys({1: {2: {3: 4}, 5: 6}})
        {'1.2.3': 4, '1.5': 6}

        v0.1.0 by bfontaine, MIT license
        """
        flat = {}
        dicts = [("", d)]

        while dicts:
            prefix, d = dicts.pop()
            for k, v in d.items():
                k_s = str(k)
                if isinstance(v, collections.Mapping):
                    dicts.append(("%s%s%s" % (prefix, k_s, sep), v))
                else:
                    k_ = prefix + k_s if prefix else k
                    flat[k_] = v
        return flat

    def _build_path(self, key='', prepend=None):
        '''Build full path of current key given the rootpath and optionally a prepend'''
        return (self.delimiter).join(filter(None, [prepend, self.rootpath, key]))

    def _build_metadata(self, fullkeys=None):
        '''Build metadata to make viewitem and other methods using item resolution faster.
        Provided a list of full keys, this method will build parent nodes to point all the way down to the leaves.
        If no list is provided, metadata will be rebuilt for the whole dict.
        Only for fastview mode.'''

        if fullkeys is None:
            fullkeys = list(self._generickeys(self.d))  # need to make a copy else RuntimeError because dict size will change

        delimiter = self.delimiter
        for fullkey in fullkeys:
            if not fullkey[-1:] == delimiter:
                # Create additional entries for each parent at every depths of the current leaf
                parents = self._get_all_parent_nodes(fullkey, self.delimiter)

                # First parent stores the direct path to the leaf
                # Then we recursively add the path to the nested parent in all super parents.
                lastparent = fullkey
                for parent in parents:
                    if parent in self.d:
                        # There is already a parent entry, we add to the set
                        self.d.__getitem__(parent).add(lastparent)
                    else:
                        # Else we create a set and add this child
                        self.d.__setitem__(parent, set([lastparent]))
                    lastparent = parent

    def _build_metadata_nodel(self, fullkeys=None):
        '''Build metadata to make contains faster.
        Provided a list of full keys, this method will build parent nodes to point all the way down to the leaves.
        If no list is provided, metadata will be rebuilt for the whole dict.
        Only for nodel mode.'''

        if fullkeys is None:
            fullkeys = list(self._generickeys(self.d))  # need to make a copy else RuntimeError because dict size will change

        delimiter = self.delimiter
        for fullkey in fullkeys:
            if not fullkey[-1:] == delimiter:
                # Create additional entries for each parent at every depths of the current leaf
                parents = self._get_all_parent_nodes(fullkey, self.delimiter)

                # First parent stores the direct path to the leaf
                # Then we recursively add the path to the nested parent in all super parents.
                for parent in parents:
                    if not parent in self.d:
                        # If parent not in dict, we create it
                        self.d.__setitem__(parent, None)

    def __getitem__(self, key):
        '''Get an item given the key. O(1) in any case: if the item is a leaf, direct access, else if it is a node, a new fdict will be returned with a different rootpath but sharing the same internal dict.'''
        fullkey = self._build_path(key)
        # Node or leaf?
        if fullkey in self.d: # Leaf: return the value (leaf direct access test is why we do `in self.d` and not `in self`)
            return self.d.__getitem__(fullkey)
        else: # Node: return a new full fdict based on the old one but with a different rootpath to limit the results by default (this is the magic that allows compatibility with the syntax d['item1']['item2'])
            return self.__class__(d=self.d, rootpath=fullkey, delimiter=self.delimiter, fastview=self.fastview, nodel=self.nodel, **self.kwargs)

    def __setitem__(self, key, value):
        '''Set an item given the key. Supports for direct setting of nested elements without prior dict(), eg, x['a/b/c'] = 1. O(1) to set the item. If fastview mode, O(m*l) because of metadata building where m is the number of parents of current leaf, and l the number of leaves (if provided a nested dict).'''
        # TODO: fastview mode can setitem buildmetadata in O(2*(l+m)) linear time instead of O(l*m) quadratic time by first walking nodes and leafs of input dict and finally just merge the nodes sets with self.d, so we walk each parent only once, instead of walking each leaf and then each parent of each leaf repetitively.
        # Build the fullkey
        fullkey = self._build_path(key)

        # Store the item
        if isinstance(value, dict):
            # if the value is a dict, flatten it recursively or drop if empty

            # First we need to delete the previous value if it was a singleton or a node
            # (so we also need to delete all subitems recursively if it was a node)
            if not self.fastview:
                if fullkey in self.d:
                    # With non-fastview fdict, can only delete singleton, not nodes
                    self.d.__delitem__(key)
            else:
                if fullkey in self:
                    self.__delitem__(key)

            # Flatten dict and store its leaves
            if not value:
                # User supplied an empty dict, the user wants to create a subdict, but it is not necessary here since nested dict are supported by default, just need to assign nested values
                return
            else:
                # else not empty dict, we will merge using update
                # merge d2 with self.d
                if isinstance(value, self.__class__):
                    # If it is the same class as this, we merge
                    d2 = self.__class__({key: value})
                    self.update(d2)
                else:
                    # If this is just a normal dict, we flatten it and merge
                    d2 = self.flatkeys({self._build_path(prepend=key) : value}, sep=self.delimiter)
                    self.d.update(d2)
                # update metadata
                if self.fastview:
                    self._build_metadata(self._generickeys(d2))
                # update metadata with nodel mode: just create empty nodes to signal the existence
                elif self.nodel:
                    self._build_metadata_nodel(self._generickeys(d2))
        else:
            # if the value is not a dict, we consider it a singleton/leaf, and we just build the full key and store the value as is
            if self.fastview:
                # Fastview mode: can ensure no conflict with a nested dict by managing the metadata
                dirkey = fullkey+self.delimiter
                # This key was a nested dict
                if dirkey in self.d:
                    # If this key was a nested dict before, we need to delete it recursively (with all subelements) and also delete pointer from parent node
                    self.__delitem__(key)
                # This key did not exist before but a parent is a singleton
                parents = self._get_all_parent_nodes(fullkey)
                for parent in parents:
                    parentleaf = parent[:len(parent)-1]
                    if parentleaf in self.d:
                        self.__delitem__(parentleaf)
                # Then we can rebuild the metadata to point to this new leaf
                self._build_metadata([fullkey])
            elif self.nodel:
                # update metadata with nodel mode: just an create empty node to signal its existence
                self._build_metadata_nodel([fullkey])
            # and finally add the singleton as a leaf
            self.d.__setitem__(fullkey, value)

    def __delitem__(self, key, fullpath=False):
        '''Delete an item in the internal dict, O(1) for any leaf, O(n) for a nested dict'''

        if self.nodel:
            # Nodel mode: remove delitem, because else the internal dict will get incoherent (ie, nodes will remain even if there is no leaf)
            # However, setitem and update will still be able to replace leaves
            return

        if not fullpath:
            fullkey = self._build_path(key)
        else:
            fullkey = key

        if fullkey in self.d:
            # Key is a leaf, we can directly delete it
            if self.fastview:
                # Remove current node from its parent node's set()
                parentnode = self._get_parent_node(fullkey, self.delimiter)
                if parentnode: # if the node is not 1st-level (because then the parent is the root, it's then a fdict, not a set)
                    self.d.__getitem__(parentnode).remove(fullkey)
                    if not self.d.__getitem__(parentnode):
                        # if the set is now empty, just delete the node (to signal that there is nothing below now)
                        self.__delitem__(parentnode, fullpath=True)  # recursive delete because the node is referenced by its parent
            # Delete the item!
            return self.d.__delitem__(fullkey)
        else:
            # Else there is no direct match, but might be a nested dict, we have to walk through all the dict
            dirkey = fullkey+self.delimiter
            flagdel = False
            if self.fastview:
                # Fastview mode: use the fast recursive viewkeys(), which will access the supplied node and walk down through all nested elements to build the list of items to delete, without having to walk the whole dict (only the subelements pointed by the current key and the subsubelements of the subkeys etc.)
                # Note that we ovveride the rootpath of viewkeys, because if delitem is called on a nested element (eg, del x['a']['b']), then the rootpath is the parent, so we will walk through all parent elements when we need only to walk from the child (the current node key), so this is both an optimization and also bugfix (because else we get a different behaviour if we use del x['a/b'] and del x['a']['b'])
                keystodel = [k for k in self.viewkeys(fullpath=True, nodes=True, rootpath=fullkey)]
                # We can already delete the current node key
                self.d.__delitem__(dirkey)
                flagdel = True
                # Remove current node from its parent node's set()
                parentnode = self._get_parent_node(fullkey, self.delimiter)
                if parentnode: # if the node is not 1st-level (because then the parent is the root, it's then a fdict, not a set)
                    self.d.__getitem__(parentnode).remove(dirkey)  # delete current node metadata
                    if not self.d.__getitem__(parentnode):
                        # if the set is now empty, just delete the node (to signal that there is nothing below now)
                        self.__delitem__(parentnode[:len(parentnode)-1], fullpath=True)  # recursive delete because the node is referenced by its parent
            else:
                # Walk through all items in the dict and delete the nodes or nested elements starting from the supplied node (if any)
                keystodel = [k for k in self._viewkeys() if k.startswith(dirkey)]  # TODO: try to optimize with a generator instead of a list, but with viewkeys the dict is changing at the same time so we get runtime error!

            # Delete all matched keys
            for k in keystodel:
                self.d.__delitem__(k)

            # Check if we deleted at least one key, else raise a KeyError exception
            if not keystodel and not flagdel:
                raise KeyError(key)
            else:
                return

    def __contains__(self, key):
        '''Check existence of a key (or subkey) in the dictionary. O(1) for any leaf, O(n) at worst for nested dicts (eg, 'a' in d with d['a/b'] defined) -- except if fastview mode or nodel mode activated'''
        fullkey = self._build_path(key)
        if self.d.__contains__(fullkey):
            # Key is a singleton/leaf, there is a direct match
            return True
        else:
            dirkey = fullkey+self.delimiter
            if self.fastview or self.nodel:
                # Fastview mode: nodes are stored so we can directly check in O(1)
                return self.d.__contains__(dirkey)
            else:
                # Key might be a node, but we have to check all items
                for k in self.viewkeys(fullpath=True):
                    if k.startswith(dirkey):
                        return True
                return False

    def viewkeys(self, fullpath=False, nodes=False, rootpath=None):
        if not rootpath:
            # Allow to override rootpath, particularly useful for delitem (which is always called from parent, so the rootpath is incorrect, overriding the rootpath allows to limit the search breadth)
            rootpath = self.rootpath

        delimiter = self.delimiter
        if not rootpath:
            if self.fastview or self.nodel:
                for k in self._viewkeys():
                    if nodes or not k[-1:] == delimiter:
                        yield k
            else:
                for k in self._viewkeys():
                    yield k
        else:
            pattern = rootpath+delimiter
            lpattern = len(pattern) if not fullpath else 0 # return the shortened path or fullpath?
            if self.fastview:
                # Fastview mode
                if pattern in self.d:
                    children = set()
                    children.update(self.d.__getitem__(pattern).copy())
                    while children:
                        child = children.pop()
                        if child[-1:] == delimiter:
                            # Node, append all the subchildren to the stack
                            children.update(self.d.__getitem__(child))
                            if nodes:
                                yield child[lpattern:]
                        else:
                            # Leaf, return the key and value
                            yield child[lpattern:]
            elif self.nodel:
                # Nodel mode: take care of nodes (ending with the delimiter) depending on nodes=False or True
                plen = len(pattern)  # if nodes, need to check if the current node is not the rootpath!
                for k in (k[lpattern:] for k in self._viewkeys() if k.startswith(pattern) and ((nodes and len(k) != plen) or not k[-1:] == delimiter)):
                    yield k
            else:
                for k in (k[lpattern:] for k in self._viewkeys() if k.startswith(pattern)):
                    yield k

    def viewitems(self, fullpath=False, nodes=False, rootpath=None):
        if not rootpath:
            # Allow to override rootpath, particularly useful for delitem (which is always called from parent, so the rootpath is incorrect, overriding the rootpath allows to limit the search breadth)
            rootpath = self.rootpath

        delimiter = self.delimiter
        if not rootpath:
            # Return all items (because no rootpath, so no filter)
            if self.fastview or self.nodel:
                # Fastview mode, filter out nodes (ie, keys ending with delimiter) to keep only leaves
                for k,v in self._viewitems():
                    if not k[-1:] == delimiter or nodes:
                        yield k,v
            else:
                # No fastview, just return the internal dict's items
                for k,v in self._viewitems():
                    yield k,v
        else:
            # Else with rootpath, filter items to keep only the ones below the rootpath level
            # Prepare the pattern (the rootpath + delimiter) to filter items keys
            pattern = rootpath+self.delimiter
            lpattern = len(pattern) if not fullpath else 0 # return the shortened path or fullpath?
            if self.fastview:
                # Fastview mode, get the list of items directly from the current entry, and walk recursively all children to get down to the leaves
                if pattern in self.d:
                    children = set()
                    children.update(self.d.__getitem__(pattern))
                    while children:
                        child = children.pop()
                        if child[-1:] == delimiter:
                            # Node, append all the subchildren to the stack
                            children.update(self.d.__getitem__(child))
                            if nodes:
                                yield child[lpattern:], set([c[lpattern:] for c in self.d.__getitem__(child)])
                        else:
                            # Leaf, return the key and value
                            yield child[lpattern:], self.d.__getitem__(child)
            elif self.nodel:
                # Nodel mode: take care of nodes (ending with the delimiter) depending on nodes=False or True
                plen = len(pattern)  # if nodes, need to check if the current node is not the rootpath!
                for k in ((k[lpattern:], v) for k,v in self._viewitems() if k.startswith(pattern) and ((nodes and len(k) != plen) or not k[-1:] == delimiter)):
                    yield k
            else:
                # No fastview, just walk through all items and filter out the ones that are not in the current rootpath
                for k,v in ((k[lpattern:], v) for k,v in self._viewitems() if k.startswith(pattern)):
                    yield k,v

    def viewvalues(self, fullpath=False, nodes=False, rootpath=None):
        if not rootpath:
            # Allow to override rootpath, particularly useful for delitem (which is always called from parent, so the rootpath is incorrect, overriding the rootpath allows to limit the search breadth)
            rootpath = self.rootpath

        delimiter = self.delimiter
        if not rootpath:
            if self.fastview or self.nodel:
                for k,v in self._viewitems():
                    if not k[-1:] == delimiter or nodes:
                        yield v
            else:
                for v in self._viewvalues():
                    yield v
        else:
            pattern = rootpath+self.delimiter
            lpattern = len(pattern) if not fullpath else 0 # return the shortened path or fullpath? useful only if nodes=True
            if self.fastview:
                # Fastview mode
                if pattern in self.d:
                    children = set()
                    children.update(self.d.__getitem__(pattern))
                    while children:
                        child = children.pop()
                        if child[-1:] == delimiter:
                            # Node, append all the subchildren to the stack
                            children.update(self.d.__getitem__(child))
                            if nodes:
                                yield set([c[lpattern:] for c in self.d.__getitem__(child)])
                        else:
                            # Leaf, return the key and value
                            yield self.d.__getitem__(child)
            elif self.nodel:
                # Nodel mode: take care of nodes (ending with the delimiter) depending on nodes=False or True
                plen = len(pattern)
                for v in (v for k,v in self._viewitems() if k.startswith(pattern) and ((nodes and len(k) != plen) or not k[-1:] == delimiter)):
                    yield v
            else:
                for v in (v for k,v in self._viewitems() if k.startswith(pattern)):
                    yield v

    iterkeys = viewkeys
    itervalues = viewvalues
    iteritems = viewitems
    if PY3:  # pragma: no cover
        keys = viewkeys
        values = viewvalues
        items = viewitems
    else:
        def keys(self, *args, **kwargs):
            return list(self.viewkeys(*args, **kwargs))
        def values(self, *args, **kwargs):
            return list(self.viewvalues(*args, **kwargs))
        def items(self, *args, **kwargs):
            return list(self.viewitems(*args, **kwargs))

    def update(self, d2):
        if isinstance(d2, self.__class__):
            # Same class, we walk d2 but we cut d2 rootpath (fullpath=False) since we will rebase on our own self.d dict
            d2items = d2.viewitems(fullpath=False, nodes=False)  # ensure we do not add nodes, we need to rebuild anyway
            d2keys = d2.viewkeys(fullpath=False, nodes=False)  # duplicate for reuse
        elif isinstance(d2, dict):
            # normal dict supplied
            d2 = self.flatkeys(d2, sep=self.delimiter) # first, flatten the dict keys
            d2items = self._genericitems(d2)
            d2keys = self._generickeys(d2)
        else:
            raise ValueError('Supplied argument is not a dict.')

        # Update our dict with d2 leaves
        if self.rootpath:
            # There is a rootpath, so user is selecting a sub dict (eg, d['item1']), so we need to reconstruct d2 with the full key path rebased on self.d before merging
            rtncode = self.d.update((self._build_path(k), v) for k,v in d2items)
        else:
            # No rootpath, we can update directly because both dicts are comparable
            if isinstance(d2, self.__class__):
                rtncode = self.d.update(d2items)
            else:
                rtncode = self.d.update(d2items)

        # Fastview mode: we have to take care of nodes, since they are set(), they will get replaced and we might lose some pointers as they will all be replaced by d2's pointers, so we have to merge them separately
        # The only solution is to skip d2 nodes altogether and rebuild the metadata for each new leaf added. This is faster than trying to merge separately each d2 set with self.d, because anyway we also have to rebuild for d2 root nodes (which might not be self.d root nodes particularly if rootpath is set)
        if self.fastview:
            self._build_metadata(self._build_path(k) for k in d2keys)
        elif self.nodel:
            self._build_metadata_nodel(self._build_path(k) for k in d2keys)

        return rtncode

    def copy(self):
        fcopy = self.__class__(d=self.d.copy(), rootpath=self.rootpath, delimiter=self.delimiter, fastview=self.fastview, nodel=self.nodel, **self.kwargs)
        if self.fastview:
            # Fastview mode: we need to ensure we have copies of every sets used for nodes, else the nodes will reference (delitem included) the same items in both the original and the copied fdict!
            for k in fcopy._viewkeys():
                if k.endswith(fcopy.delimiter):
                    fcopy.d[k] = fcopy.d[k].copy()
        return fcopy

    @staticmethod
    def _count_iter_items(iterable):
        '''
        Consume an iterable not reading it into memory; return the number of items.
        by zuo: https://stackoverflow.com/a/15112059/1121352
        '''
        counter = itertools.count()
        collections.deque(_zip(iterable, counter), maxlen=0)  # (consume at C speed)
        return next(counter)

    def __len__(self):
        if not self.rootpath and (not self.fastview and not self.nodel):
            return self.d.__len__()
        else:
            # If there is a rootpath, we have to limit the length to the subelements
            return self._count_iter_items(self.viewkeys())

    def __eq__(self, d2):
        # Note that if using fastmode and you want to compare an extract(), you cannot compare the nodes unless you fdict(d2)!
        is_fdict = isinstance(d2, self.__class__)
        is_dict = isinstance(d2, dict)
        if not is_dict and not is_fdict:
            # If not a dict nor a subclass of fdict, we cannot compare
            return False
        else:
            if is_fdict and not self.rootpath and self.fastview == d2.fastview and self.nodel == d2.nodel:
                # fdict, we can directly compare the internal dicts (but only if fastview is the same for both)
                return (self.d == d2.d)
            else:
                kwargs = {}
                if is_fdict:
                    if len(self) != len(d2) and self.fastview == d2.fastview and self.nodel == d2.nodel:
                        # If size is different then the dicts are different
                        # Note that we need to compare the items because we need to filter if we are looking at nested keys (ie, if there is a rootpath)
                        return False
                    else:
                        kwargs['fullpath'] = False
                else:  # normal dict, need to flatten it first
                    d2 = self.__class__.flatkeys(d2, sep=self.delimiter)
                    if len(self) != len(d2):
                        return False

                # Else size is the same, check each item if they are equal
                # BTW, we use viewitems to filter according to rootpath the items we compare (else we will compare the full dict to d2 if d2 is a fdict, which is probably not what the user wants if he does d['item1'] == d2)
                d2items = self._genericitems(d2, **kwargs)
                for k, v in d2items:
                    fullkey = self._build_path(k)
                    if not fullkey in self.d or self.d.__getitem__(fullkey) != v:
                        return False
                return True

    def __ne__(self, d2):
        return not self == d2  # do not use self.__eq__(d2), for more infos see https://stackoverflow.com/questions/4352244/python-should-i-implement-ne-operator-based-on-eq/30676267#30676267

    def __repr__(self, nodes=True):
        # Filter the items if there is a rootpath and return as a new fdict
        if self.rootpath:
            return repr(dict(self.items(fullpath=False, nodes=nodes)))
        else:
            try:
                return self.d.__repr__()
            except (AttributeError, TypeError):
                return repr(dict(self.items()))

    def __str__(self, nodes=False):
        if self.rootpath:
            return str(dict(self.items(fullpath=False, nodes=nodes)))
        else:
            try:
                return self.d.__str__()
            except (AttributeError, TypeError):
                return str(dict(self.items()))

    def pop(self, k, d=None, fullpath=True):
        fullkey = self._build_path(k)
        if fullkey in self.d:
            # Leaf
            if not self.fastview:
                res = self.d.pop(fullkey)
            else:
                res = self.d.__getitem__(fullkey)
                self.__delitem__(fullkey, fullpath=True)  # need to rebuild the metadata
        else:
            # Node
            if self.fastview and fullkey+self.delimiter not in self.d:
                res = None
            else:
                # We can check with fastview if the node exists beforehand
                res = self.__getitem__(k).extract(fullpath=fullpath)
                if res:
                    self.__delitem__(fullkey, fullpath=True)

        if res:
            return res
        else:
            return d

    def popitem(self):
        if not self.fastview:
            return self.d.popitem()
        else:
            try:
                k, v = next(self.viewitems(fullpath=False, nodes=False))
                self.__delitem__(k)  # need to update the metadata
                return k, v
            except StopIteration:
                raise KeyError('popitem(): dictionary is empty')

    def to_dict(self):
        '''Convert to a flattened dict'''
        return dict(self.items())

    def extract(self, fullpath=True):
        '''Return a new fdict shortened to only the currently subselected items, but instead of fdict, should also support sfdict or any child class
        It was chosen to return a fdict still containing the full keys and not the shortened ones because else it becomes very difficult to merge fdicts
        And also for subdicts (like sfdict) which might store in a file, so we don't want to start mixing up different paths in the same file, but we would like to extract to a fdict with same parameters as the original, so keeping full path is the only way to do so coherently.
        '''
        if fullpath:
            d2 = self.__class__(d=self.items(fullpath=True, nodes=False), rootpath=self.rootpath, delimiter=self.delimiter, fastview=self.fastview, nodel=self.nodel, **self.kwargs)
        else:
            d2 = self.__class__(d=self.items(fullpath=False, nodes=False), rootpath='', delimiter=self.delimiter, fastview=self.fastview, nodel=self.nodel) # , **self.kwargs)  # if not fullpath for keys, then we do not propagate kwargs because it might implicate propagating filename saving and mixing up keys. For fdict, this does not make a difference, but it might for subclassed dicts. Override this function if you want to ensure that an extract has all same parameters as original when fullpath=False in your subclassed dict.
        if d2.fastview:
            d2._build_metadata()
        return d2

    def to_dict_nested(self):
        '''Convert to a nested dict'''
        d2 = {}
        delimiter = self.delimiter
        # Constuct the nested dict for each leaf
        for k, v in self.viewitems(nodes=False):
            # Get all parents of the current leaf, from root down to the leaf's direct parent
            parents = self._get_all_parent_nodes_nested(k, delimiter)
            # Recursively create each node of this subdict branch
            d2sub = d2
            for parent in parents:
                if not parent in d2sub:
                    # Create the node if it does not exist
                    d2sub[parent] = {}
                # Continue from this node
                d2sub = d2sub[parent]
            # get leaf key
            k = k[k.rfind(delimiter)+1:]
            # set leaf value
            d2sub[k] = v
        return d2


class sfdict(fdict):
    '''
    A nested dict with flattened internal representation, combined with shelve to allow for efficient storage and memory allocation of huge nested dictionnaries.
    If you change leaf items (eg, list.append), do not forget to sync() to commit changes to disk and empty memory cache because else this class has no way to know if leaf items were changed!
    '''
    def __init__(self, *args, **kwargs):
        '''
        Parameters
        ----------
        d  : dict, optional
            Initialize with a pre-existing dict.
            Also used internally to pass a reference to parent fdict.
        rootpath : str, optional
            Internal variable, define the nested level.
        delimiter  : str, optional
            Internal delimiter for nested levels. Can also be used for
            getitem direct access (e.g. ``x['a/b/c']``).
            [default : '/']
        fastview  : bool, optional
            Activates fastview mode, which makes setitem slower
            in O(m*l) instead of O(1), but makes view* methods
            (viewitem, viewkeys, viewvalues) as fast as dict's.
            [default : False]
        nodel  : bool, optional
            Activates nodel mode, which makes contains test
            in O(1) for nodes (leaf test is always O(1) in any mode).
            Only drawback: delitem is not suppressed.
            Useful for quick building of databases, then you can
            reopen the database with a normal fdict if you want
            the ability to delitem.
            [default : False]
        filename : str, optional
            Path and filename where to store the database.
            [default : random temporary file]
        autosync : bool, optional
            Commit (sync) to file at every setitem (assignment).
            Assignments are always stored on-disk asap, but not
            changes to non-dict collections stored in leaves
            (e.g. updating a list stored in a leaf will not commit to disk).
            This option allows to sync at the next assignment automatically
            (because there is no way to know if a leaf collection changed).
            Drawback: if you do a lot of assignments, this will significantly
            slow down your processing, so it is advised to rather sync()
            manually at regular intervals.
            [default : False]
        writeback : bool, optional
            Activates shelve writeback option. If False, only assignments
            will allow committing changes of leaf collections. See shelve
            documentation.
            [default : True]
        forcedumbdbm : bool, optional
            Force the use of the Dumb DBM implementation to manage
            the on-disk database (should not be used unless you get an
            exception because not any other implementation of anydbm
            can be found on your system). Dumb DBM should work on
            any platform, it is native to Python.
            [default : False]
        Returns
        -------
        out  : dict-like object.
        '''
        # Initialize specific arguments for sfdict
        if 'filename' in kwargs:
            self.filename = kwargs['filename']
            #del kwargs['filename'] # do not del for auto management of internal sub calls to sfdict
        else:
            # No filename was supplied, create a temporary file
            file = tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix='.shelve')
            self.filename = file.name
            file.close()
            # always remove temporary file before opening the db (else we get an error because the file has an unrecognized db format)
            os.remove(self.filename)

        if 'autosync' in kwargs:
            # Autosync changes back to the db file? By default false because it would be inefficient.
            self.autosync = kwargs['autosync']
        else:
            self.autosync = False

        if 'writeback' in kwargs:
            # Writeback allows to monitor nested objects changes, such as list.append(), without writeback all changes must be done by direct assignment: tmp = a['a'], tmp.append(3), a['a'] = tmp
            self.writeback = kwargs['writeback']
        else:
            self.writeback = True

        if 'forcedumbdbm' in kwargs:
            # Force the use of dumbdbm, a generic implementation available on all platforms (but slow)?
            self.forcedumbdbm = kwargs['forcedumbdbm']
        else:
            self.forcedumbdbm = False

        # Initialize parent class
        super(sfdict, self).__init__(*args, **kwargs)

        # Initialize the out-of-core shelve database file
        if not self.rootpath: # If rootpath, this is an internal call, we just reuse the input dict
            # Else it is an external call, we reuse the provided dict but we make a copy and store in another file, or there is no provided dict and we create a new one
            try:
                if self.forcedumbdbm:
                    # Force the use of dumb dbm even if slower
                    raise ImportError('pass')
                d = shelve.open(filename=self.filename, flag='c', protocol=PICKLE_HIGHEST_PROTOCOL, writeback=self.writeback)
                self.usedumbdbm = False
            except (ImportError, IOError) as exc:
                if 'pass' in str(exc).lower() or '_bsddb' in str(exc).lower() or 'permission denied' in str(exc).lower():
                    # Pypy error, we workaround by using a fallback to anydbm: dumbdbm
                    if PY3:  # pragma: no cover
                        from dbm import dumb
                        db = dumb.open(self.filename, 'c')
                    else:
                        import dumbdbm
                        db = dumbdbm.open(self.filename, 'c')
                    # Open the dumb db as a shelf
                    d = shelve.Shelf(db, protocol=PICKLE_HIGHEST_PROTOCOL, writeback=self.writeback)
                    self.usedumbdbm = True
                else:  # pragma: no cover
                    raise

            # Initialize the shelve with the internal dict preprocessed by the parent class fdict
            d.update(self.d)
            # Then update self.d to use the shelve instead
            del self.d
            self.d = d
            self.d.sync()

        # Call compatibility layer
        self._viewkeys, self._viewvalues, self._viewitems = self._getitermethods(self.d)

    def __setitem__(self, key, value):
        super(sfdict, self).__setitem__(key, value)
        if self.autosync:
            # Commit pending changes everytime we set an item
            self.sync()

    def get_filename(self):
        return self.filename

    def sync(self):
        '''Commit pending changes to file'''
        self.d.sync()

    def close(self, delete=False):
        '''Commit pending changes to file and close it'''
        self.d.close()
        if delete:
            try:
                filename = self.get_filename()
                if not self.usedumbdbm:
                    os.remove(filename)
                else:
                    os.remove(filename+'.dat')
                    os.remove(filename+'.dir')
                    if os.path.exists(filename+'.bak'):  # pragma: no cover
                        os.remove(filename+'.bak')
            except Exception:  # pragma: no cover
                pass
