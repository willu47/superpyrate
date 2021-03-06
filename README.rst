===========
superpyrate
===========

.. image:: https://travis-ci.org/UCL-ShippingGroup/superpyrate.svg?branch=master
    :target: https://travis-ci.org/UCL-ShippingGroup/superpyrate

.. image:: https://readthedocs.org/projects/superpyrate/badge/?version=latest
    :target: http://superpyrate.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

Does what pyrate does, but supercharged.




Description
===========

Superpyrate ingests AIS data in parallel to a postgres database, and provides
a framework for running algorithms and tasks on this AIS data.

Superpyrate rests heavily on luigi_, a pipeline and dataflow manager which
uses large directed acyclic graphs model and manage the flows of data between tasks.

.. _luigi: http://luigi.readthedocs.io/en/stable/


Dependencies
============

Postgres 9.5.3
--------------

7zip
----


Quick Start
===========

Install the library using::

    python setup.py develop

Start your :py:mod:`luigi` server and populate the environment variables with
the postgres database details.  Then run::

    luigi --module superpyrate.pipeline ClusterAisClean \
    --workers 4
    --folder_of_zips path/to/folder
