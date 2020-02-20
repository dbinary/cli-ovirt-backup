import click

@click.command()
def hello():
    click.echo('hello World!')

if __name__ == '__main__':
    hello()
