#!/usr/bin/env python
from setuptools import setup


setup(
    name='SpotifyWebsocketAPI',
    version='0.2',
    author='Liam McLoughlin',
    author_email='hexxeh@hexxeh.net',
    packages=['spotify_web', 'spotify_web.proto'],
    install_requires=[
        'requests>=1.1.0',
        'ws4py>=0.2.4',
        'lxml>=3.1beta1',
        'protobuf>=2.4.1'],
)
