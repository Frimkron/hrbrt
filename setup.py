import os.path
import setuptools
from hrbrt import VERSION

here = os.path.abspath(os.path.dirname(__file__))

setuptools.setup(

    name='hrbrt',
    version=VERSION,
    description='Parses and displays documents in HRBrT: a text-based '
                'format for describing a graph of text nodes with choices'
    long_description=open(os.path.join(here, 'readme.md'), encoding='utf-8').read(),
    author='Mark Frimston',
    author_email='mark@markfrimston.co.uk',
    url='https://github.com/frimkron/hrbrt',
    license='MIT',

    packages=['hrbrt'],
    install_requires=[],
    python_requires='>=2.7,<3.0',
    entry_points={
        'console_scripts': [
            'hrbrt = hrbrt.__main__:main'
        ],
    },
)
