import click


@click.group()
def cli():
    pass


@cli.command()
@click.argument('vmname')
@click.option(
    '--username', '-u', envvar='OVIRTUSER', help='username for oVirt API'
)
@click.option(
    '--password', '-p', envvar='OVIRTPASS', help='password for oVirt user'
)
def backup(username, password, vmname):
    click.echo(username)


@cli.command()
def restore():
    click.echo('restore')
