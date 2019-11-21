.. image:: https://travis-ci.org/anjos/lighter.svg?branch=master
   :target: https://travis-ci.org/anjos/lighter
.. image:: https://img.shields.io/docker/pulls/anjos/lighter.svg
   :target: https://hub.docker.com/r/anjos/lighter/

---------
 Lighter
---------

A bunch of utilities to help me configure and control my ZigBee network at
home, via deCONZ_ and the Phoscon_ gateway, from `Dresden Elektronik`_,
Germany.  This tool is written in Python using pydeconz_, which are
python-REST-ful-API bindings.


Installation
------------

I advise you to install a Conda_-based environment for deployment with this
command line::

  $ conda create --override-channels -c anjos -c defaults -n lighter python=3.7 lighter

Once the environment is installed, activate it to be able to call binaries::

  $ source activate lighter


Usage
-----

There is a single program that you can launch::

  $ ./bin/lighter --help

And a complete help message will be displayed.


Development
-----------

I advise you to install a Conda_-based environment for development with this
command line::

  $ conda env create -f dev.yml


Build
=====

To build the project and make it ready to run, do::

  $ source activate lighter-dev
  $ buildout

This command should leave you with a functional environment.


Conda Builds
============

Building dependencies requires you install ``conda-build``. Do the following to
prepare::

  $ conda install -n base conda-build anaconda-client

Then, you can build dependencies one by one, in order::

  $ conda activate base
  $ conda build conda


Anaconda Uploads
================

To upload all built dependencies (so you don't have to re-build them
everytime), do::

  (base) $ anaconda login
  # enter credentials
  (base) $ anaconda upload <conda-bld>/noarch/lighter-*.tar.bz2


.. Place your references after this line
.. _deconz: https://github.com/dresden-elektronik/deconz-rest-plugin
.. _deconz-api-doc: https://dresden-elektronik.github.io/deconz-rest-doc/
.. _phoscon: https://www.dresden-elektronik.de/funktechnik/solutions/wireless-light-control/gateways/phoscon-gateway/
.. _dresden elektronik: https://www.dresden-elektronik.de
.. _conda: http://conda.pydata.org/miniconda.html
.. _pydeconz: https://github.com/Kane610/deconz
