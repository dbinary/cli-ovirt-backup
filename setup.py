from setuptools import setup

setup(
    name='cliobr',
    version='0.1',
    py_modules=['cliobr'],
    install_requires=[
        'Click',
        'ovirt-engine-sdk-python'
    ],
    entry_points='''
        [console_scripts]
        cliobr=cliobr:hello
    ''',
)
