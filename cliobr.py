import datetime
import os
import click
import logging
import ovirtsdk4 as sdk
import ovirtsdk4.types as types


FORMAT = '%(asctime)s %(levelname)s %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT, filename='example.log')


@click.group()
def cli():
    pass


@cli.command()
@click.argument('vmname')
@click.option(
    '--username', '-u', envvar='OVIRTUSER', default='admin@internal', show_default=True, help='username for oVirt API'
)
@click.option(
    '--password', '-p', envvar='OVIRTPASS', required=True, help='password for oVirt user'
)
@click.option(
    '--ca', '-c', envvar='OVIRTCA', required=True, type=click.Path(), help='path for ca certificate of Manager'
)
@click.option(
    '--url', '-U', envvar='OVIRTURL', required=True, help='url for oVirt API'
)
@click.option('--debug', is_flag=True, default=False, help='debug mode')
def backup(username, password, ca, vmname, url, debug):
    connection = sdk.Connection(
        url=url,
        username=username,
        password=password,
        ca_file=ca,
        debug=debug,
        log=logging.getLogger(),
    )
    logging.info('Connected to the server.')
    click.echo('Connected to the server.')


@cli.command()
@click.argument('vmname')
@click.option(
    '--username', '-u', envvar='OVIRTUSER', help='username for oVirt API'
)
@click.option(
    '--password', '-p', envvar='OVIRTPASS', help='password for oVirt user'
)
def restore(username, password, vmname):
    click.echo('{} {} {}'.format(username, password, vmname))
