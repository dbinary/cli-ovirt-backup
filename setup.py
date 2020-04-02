from setuptools import setup, find_packages

setup(
    author='Luis Pérez Marin',
    author_email='luis.perez@protonmail.com',
    keywords=['backup', 'restore', 'ovirt', 'virtualization'],
    long_description='Script for backup and restore virtual machines in oVirt/RHV environment',
    name='cliobr',
    version='0.8.2',
    description='Script for backup and restore virtual machines in oVirt/RHV environment',
    py_modules=['cliobr', 'helpers'],
    license='MIT',
    install_requires=[
        'Click',
        'ovirt-engine-sdk-python',
        'click-shell'
    ],
    entry_points='''
        [console_scripts]
        cliobr=cliobr:cli
    ''',
)
