# IMPORTANT: for compatibility with `python setup.py make [alias]`, ensure:
# 1. Every alias is preceded by @[+]make (eg: @make alias)
# 2. A maximum of one @make alias or command per line
#
# Sample makefile compatible with `python setup.py make`:
#```
#all:
#	@make test
#	@make install
#test:
#	nosetest
#install:
#	python setup.py install
#```

.PHONY:
	alltests
	all
	flake8
	test
	testnose
	testsetup
	testcoverage
	testperf
	testtimer
	distclean
	coverclean
	prebuildclean
	clean
	installdev
	install
	build
	pypimeta
	pypi
	none

help:
	@python setup.py make

alltests:
	@+make testcoverage
	@+make testperf
	@+make flake8
	@+make testsetup

all:
	@+make alltests
	@+make build

flake8:
	@+flake8 --max-line-length=80 --count --statistics --exit-zero -j 8 --exclude .asv .

test:
	tox --skip-missing-interpreters

testnose:
	nosetests fdict -d -v

testsetup:
	python setup.py check --restructuredtext --strict
	python setup.py make none

testcoverage:
	@make coverclean
	nosetests fdict --with-coverage --cover-package=fdict --cover-erase --cover-min-percentage=80 --ignore-files="tests_perf\.py" -d -v

testperf:  # do not use coverage (which is extremely slow)
	nosetests fdict/tests/tests_perf.py -d -v

testtimer:
	nosetests fdict --with-timer -d -v

testasv:
	asv run -j 8 HEAD~3..HEAD
	@make viewasv

testasvfull:
	asv run -j 8 v1.0.0..master
	@make testasv

viewasv:
	asv publish
	asv preview

distclean:
	@+make coverclean
	@+make prebuildclean
	@+make clean
prebuildclean:
	@+python -c "import shutil; shutil.rmtree('build', True)"
	@+python -c "import shutil; shutil.rmtree('dist', True)"
	@+python -c "import shutil; shutil.rmtree('fdict.egg-info', True)"
coverclean:
	@+python -c "import os; os.remove('.coverage') if os.path.exists('.coverage') else None"
clean:
	@+python -c "import os; import glob; [os.remove(i) for i in glob.glob('*.py[co]')]"
	@+python -c "import os; import glob; [os.remove(i) for i in glob.glob('fdict/*.py[co]')]"
	@+python -c "import os; import glob; [os.remove(i) for i in glob.glob('fdict/tests/*.py[co]')]"
	@+python -c "import os; import glob; [os.remove(i) for i in glob.glob('fdict/examples/*.py[co]')]"

installdev:
	python setup.py develop --uninstall
	python setup.py develop

install:
	python setup.py install

build:
	@make prebuildclean
	python setup.py sdist --formats=gztar,zip bdist_wheel
	python setup.py bdist_wininst

pypimeta:
	python setup.py register

pypi:
	twine upload dist/*

buildupload:
	@make testsetup
	@make build
	@make pypimeta
	@make pypi

none:
	# used for unit testing
