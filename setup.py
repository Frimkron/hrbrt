#!/usr/bin/env python3

import os.path
import setuptools
from hrbrt import VERSION

here = os.path.abspath(os.path.dirname(__file__))

setuptools.setup(

    name='hrbrt',
    version='.'.join(map(str,VERSION)),
    description='Parses and displays documents in HRBrT: a text-based '
                'format for describing a graph of text nodes with choices',
    long_description=open(os.path.join(here, 'README.md'), encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    author='Mark Frimston',
    author_email='mark@markfrimston.co.uk',
    url='https://github.com/frimkron/hrbrt',
    license='MIT',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='parser branching multiple choice document format quiz questionnaire dialogue tree',
    packages=['hrbrt'],
    install_requires=[],
    python_requires='>=3.6',
    test_suite='tests',
    entry_points={
        'console_scripts': [
            'hrbrt = hrbrt.__main__:main.start'
        ],
    },
)
