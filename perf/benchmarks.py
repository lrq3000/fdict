import re
import sys
import timeit

from fdict import fdict, sfdict

### UTILS
def timeit_auto(stmt="pass", setup="pass", repeat=3):
    """
    http://stackoverflow.com/q/19062202/190597 (endolith)
    Imitate default behavior when timeit is run as a script.

    Runs enough loops so that total execution time is greater than 0.2 sec,
    and then repeats that 3 times and keeps the lowest value.

    Returns the number of loops and the time for each loop in microseconds
    """
    t = timeit.Timer(stmt, setup)

    # determine number so that 0.2 <= total time < 2.0
    for i in range(1, 10):
        number = 10**i
        x = t.timeit(number) # seconds
        if x >= 0.2:
            break
    r = t.repeat(repeat, number)
    best = min(r)
    usec = best * 1e6 / number
    return number, usec

def format_sizeof(num):
    '''
    Formats a number to standard time format
    '''
    units_delim = ((1000, ['usec', 'msec']), (60, ['sec', 'min']), (24, ['hrs']), (30, ['days']), (12, ['months']), (99999, ['years']))
    
    for delimiter, units in units_delim:
        for unit in units:
            if abs(num) < delimiter:
                return '{0:3.2f} '.format(num) + unit
            num /= delimiter
    return '{0:3.2f} '.format(num) + unit

### BENCHMARKS
try:
    _range = xrange
except NameError as exc:
    _range = range

def benchmark_set(dclass, breadth=5, depth=1000, args=[], kwargs={}):
    '''Test performance of setitem with indirect access of nested elements (eg: x['a']['b']['c'])'''
    d = dclass(*args, **kwargs)
    di = d
    for i in _range(depth):
        for j in _range(breadth):
            di[str(j)] = j
        di[str(breadth)] = {}
        di = di[str(breadth)]
    return d

def benchmark_get(dclass, breadth=5, depth=1000, d=None, args=[], kwargs={}):
    '''Test performance of getitem with indirect access of nested elements (eg: x['a']['b']['c'])'''
    if d is None:
        d = benchmark_set(dclass, breadth=breadth, depth=depth, args=args, kwargs=kwargs)
    di = d
    x = None
    for i in _range(depth):
        for j in _range(breadth):
            x = di[str(j)]
        di = di[str(breadth)]
    return d

def benchmark_set_direct(dclass, breadth=5, depth=1000, delimiter='/', args=[], kwargs={}):
    '''Test performance of setitem with direct access of nested elements (using strings with delimiter, eg: x['a/b/c'])'''
    d = dclass(*args, **kwargs)
    rootpath = ''
    for i in _range(depth):
        delim = (delimiter if i>0 else '')
        for j in _range(breadth):
            d[rootpath+delim+str(j)] = j
        rootpath += delim+str(breadth)
    return d

def benchmark_get_direct(dclass, breadth=5, depth=1000, d=None, delimiter='/', args=[], kwargs={}):
    '''Test performance of getitem with direct access of nested elements (using strings with delimiter, eg: x['a/b/c'])'''
    if d is None:
        d = benchmark_set_direct(dclass, breadth=breadth, depth=depth, delimiter=delimiter, args=args, kwargs=kwargs)
    rootpath = ''
    x = None
    for i in _range(depth):
        delim = (delimiter if i>0 else '')
        for j in _range(breadth):
            x = d[rootpath+delim+str(j)] 
        rootpath += delim+str(breadth)
    return d

def benchmark_viewitems_dict(dclass, breadth=5, depth=1000, d=None, args=[], kwargs={}):
    '''Test performance of viewitems on dict'''
    if d is None:
        d = benchmark_set(dclass, breadth=breadth, depth=depth, args=args, kwargs=kwargs)
    x = 0
    di = d
    for i in _range(depth):
        for _ in di.viewitems():
            x += 1
        di = di[str(breadth)]
    return x

def benchmark_viewitems_fdict(dclass, breadth=5, depth=1000, d=None, args=[], kwargs={}):
    '''Test performance of viewitems on fdict'''
    if d is None:
        d = benchmark_set_direct(dclass, breadth=breadth, depth=depth, args=args, kwargs=kwargs)
    x = 0
    di = d
    for i in _range(depth):
        for _ in di.viewitems():
            x += 1
        di = di[str(breadth)]
    return x

### DEFINE BENCHMARKS

tests = '''
### setitem and getitem indirect access, eg, x['a']['b']['c']
## dict
# setitem
benchmark_set(dict, depth=100)
# getitem+setitem
benchmark_get(dict, depth=100, d=benchmark_set(dict, depth=100))
## fdict
# setitem
benchmark_set(fdict, depth=100)
# getitem+setitem
benchmark_get(fdict, depth=100, d=benchmark_set(fdict, depth=100))
## fdict fastview (skipped because too slow! setitem runs in quadratic time because of metadata building, but can be optimized to run in linear time!)
# setitem
#benchmark_set(fdict, depth=100, kwargs={'fastview': True})
# getitem+setitem
#benchmark_get(fdict, depth=100, d=benchmark_set(fdict, depth=100, kwargs={'fastview': True}))

### setitem and getitem direct access, eg, x['a/b/c']
## dict
# setitem
benchmark_set_direct(dict, depth=100)
# getitem+setitem
benchmark_get_direct(dict, depth=100, d=benchmark_set_direct(dict, depth=100))
## fdict
# setitem
benchmark_set_direct(fdict, depth=100)
# getitem+setitem
benchmark_get_direct(fdict, depth=100, d=benchmark_set_direct(fdict, depth=100))
## fdict fastview
# setitem
#benchmark_set_direct(fdict, depth=100, kwargs={'fastview': True})
# getitem+setitem
#benchmark_get_direct(fdict, depth=100, d=benchmark_set_direct(fdict, depth=100, kwargs={'fastview': True}))

### viewitem
## dict
benchmark_viewitems_dict(dict, breadth=100, depth=5, d=benchmark_set(dict, breadth=100, depth=5))
## fdict
benchmark_viewitems_fdict(fdict, breadth=100, depth=5, d=benchmark_set_direct(fdict, breadth=100, depth=5))
## fdict fastview
#benchmark_viewitems_fdict(fdict, breadth=100, depth=5, d=benchmark_set_direct(fdict, breadth=100, depth=5, kwargs={'fastview': True}))

'''

### RUN BENCHMARKS
# Get all functions starting with 'benchmark_'
all_benchmarks = ', '.join([s for s in dir() if s.startswith('benchmark_')])

# Extract statements from the tests docstring
tests_stmts = [x for x in  re.split(r'\s+(#+.+?\n)(?=[^#])', tests, flags=(re.M | re.S)) if x.strip()]

# Build the setup string (imports etc) for the timeit
setupstr = 'from fdict import fdict, sfdict\nfrom __main__ import %s' % all_benchmarks

for test in tests_stmts:
    if test[0] == '#':
        # Comment, just print it
        print(test.strip('\n'))
        continue
    else:
        # A real test statement, we process it
        num, timing = timeit_auto(setup=setupstr, stmt=test)
        print('%i loops, best of 3: %s' % (num, format_sizeof(timing)))

sys.exit(0)