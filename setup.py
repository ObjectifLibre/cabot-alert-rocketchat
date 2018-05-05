#!/usr/bin/env python

from setuptools import setup, find_packages

def readme():
    with open('README.rst') as f:
        return f.read()

setup(name='cabot-alert-rocketchat',
      version='0.0.2',
      description='A RocketChat alert plugin for Cabot',
      long_description=readme(),
      license='MIT',
      author='Objectif Libre',
      author_email='flavien.hardy@objectif-libre.com',
      url='https://objectif-libre.com',
      packages=find_packages(),
     )
