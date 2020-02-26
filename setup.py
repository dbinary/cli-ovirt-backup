from setuptools import setup, find_packages

setup(
    name='cliobr',
    version='0.1',
    description='Script for backup and restore virtual machines in oVirt/RHV environment',
    py_modules=['cliobr'],
    license='MIT',
    install_requires=[
        'Click',
        'ovirt-engine-sdk-python'
    ],
    entry_points='''
        [console_scripts]
        cliobr=cliobr:cli
    ''',
)
