#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

from setuptools import setup, find_packages

setup(
    name="lighter",
    version="0.1.0",
    description="Utilities for managing the ZigBee home stuff",
    url="https://github.com/anjos/lighter",
    license="GPLv3",
    author="Andre Anjos",
    author_email="andre.dos.anjos@gmail.com",
    long_description=open("README.rst").read(),
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        "setuptools",
        "click>=7",
        "click-plugins",
        "requests",
        "termcolor",
        "pyyaml>=5.1",
        "python-dateutil",
        "tqdm",
    ],
    entry_points={
        "console_scripts": ["lighter = lighter.scripts.lighter:main"],
        "lighter.cli": [
            'config = lighter.scripts.config:config',
            'lights = lighter.scripts.lights:lights',
            'groups = lighter.scripts.groups:groups',
            'scenes = lighter.scripts.scenes:scenes',
            ],
        "lighter.config.cli": [
            'get = lighter.scripts.config:get',
            'apikey = lighter.scripts.config:apikey',
            ],
        "lighter.lights.cli": [
            'get = lighter.scripts.lights:get',
            'name = lighter.scripts.lights:name',
            'state = lighter.scripts.lights:state',
            ],
        "lighter.groups.cli": [
            'get = lighter.scripts.groups:get',
            'name = lighter.scripts.groups:name',
            'member = lighter.scripts.groups:member',
            'state = lighter.scripts.groups:state',
            'scene = lighter.scripts.groups:scene',
            ],
        "lighter.scenes.cli": [
            'get = lighter.scripts.scenes:get',
            'set = lighter.scripts.scenes:set',
            'setmany = lighter.scripts.scenes:setmany',
            'recall = lighter.scripts.scenes:recall',
            ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
    ],
)
