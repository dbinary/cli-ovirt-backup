import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from time import sleep

import click
import ovirtsdk4 as sdk
import ovirtsdk4.types as types
import platform
from click_shell import shell

import helpers

FORMAT = '%(asctime)s %(levelname)s %(message)s'
AgentVM = platform.node()
Description = 'cli-ovirt-backup'
VERSION = '0.8.3'
ONERROR = 0


def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo(VERSION)
    ctx.exit()


# @click.group()
@shell(prompt='cliobr => ', intro='Starting cliobr shell...')
@click.option('--version', '-v', is_flag=True, callback=print_version, expose_value=False, is_eager=True)
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
    '--api', '-a', envvar='OVIRTURL', required=True, help='url for oVirt API https://manager.example.com/ovirt-engine/api'
)
@click.option(
    '--backup-path', '-b', envvar='BACKUPPATH', type=click.Path(), default='/ovirt-backup', show_default=True, help='path of backups'
)
@click.option(
    '--log', '-l', envvar='OVIRTLOG', type=click.Path(), default='/var/log/cli-ovirt-backup.log', show_default=True, help='path log file'
)
@click.option('--debug', '-d', is_flag=True, default=False, help='debug mode')
@click.option('--unarchive', '-n', is_flag=True, default=False, help='archive backup')
def backup(username, password, ca, vmname, api, debug, backup_path, log, unarchive):
    logging.basicConfig(level=logging.DEBUG, format=FORMAT,
                        filename=log)
    connection = sdk.Connection(
        url=api,
        username=username,
        password=password,
        ca_file=ca,
        debug=debug,
        log=logging.getLogger(),
    )

    # id for event in virt manager
    event_id = int(time.time())

    logging.info('[{}] Connected to the server.'.format(event_id))
    if debug:
        click.echo('[{}] Connected to the server.'.format(event_id))

    # Get the reference to the root of the services tree:
    system_service = connection.system_service()

    # Get the reference to the service that we will use to send events to
    # the audit log:
    events_service = system_service.events_service()

    # Get the reference to the service that manages the virtual machines:
    vms_service = system_service.vms_service()

    vm = helpers.vmobj(vms_service, vmname)

    message = (
        '[{}] Backup of virtual machine \'{}\' using snapshot \'{}\' is '
        'starting.'.format(event_id, vm.name, Description)
    )
    helpers.send_events(events_service, event_id,
                        types, Description, message, vm)

    timestamp = time.strftime("%Y%m%d%H%M%S")
    backup_path_obj = Path(backup_path)
    backup_name_obj = Path(vmname + '-' + timestamp)
    vm_backup_obj = backup_path_obj / backup_name_obj
    vm_backup_absolute = vm_backup_obj.absolute().as_posix()

    if not backup_path_obj.exists():
        logging.error("[{}] Mount point {} not exists".format(
            event_id, backup_path_obj.name))
        exit(1)

    logging.info(
        '[{}] Found data virtual machine \'{}\', the id is \'{}\'.'.format(
            event_id, vm.name, vm.id)
    )
    if debug:
        click.echo(
            '[{}] Found data virtual machine \'{}\', the id is \'{}\'.'.format(event_id, vmname, vm.id))
    vmAgent = helpers.vmobj(vms_service, AgentVM)
    logging.info(
        '[{}] Found agent virtual machine \'{}\', the id is \'{}\'.'.format(event_id,
                                                                            vmAgent.name, vmAgent.id)
    )
    if debug:
        click.echo(
            '[{}] Found agent virtual machine \'{}\', the id is \'{}\'.'.format(event_id, vmAgent.name, vmAgent.id))

    helpers.createdir(vm_backup_absolute)
    logging.info('[{}] Creating directory {}.'.format(
        event_id, vm_backup_absolute))
    if debug:
        click.echo('[{}] Creating directory {}.'.format(
            event_id, vm_backup_absolute))
    # Find the services that manage the data and agent virtual machines:
    data_vm_service = vms_service.vm_service(vm.id)
    agent_vm_service = vms_service.vm_service(vmAgent.id)

    ovf_file = helpers.writeconfig(vm, vm_backup_absolute + '/')
    logging.info('[{}] Wrote OVF to file \'{}\''.format(event_id, ovf_file))
    if debug:
        click.echo('[{}] Wrote OVF to file \'{}\''.format(event_id, ovf_file))

    snaps_service = data_vm_service.snapshots_service()

    snap = helpers.createsnapshot(snaps_service, types, Description)
    logging.info('[{}] Sent request to create snapshot \'{}\', the id is \'{}\'.'.format(
        event_id, snap.description, snap.id))
    if debug:
        click.echo('[{}] Sent request to create snapshot \'{}\', the id is \'{}\'.'.format(
            event_id, snap.description, snap.id))

    snap_service = snaps_service.snapshot_service(snap.id)
    helpers.waitingsnapshot(snap, types, logging, time,
                            snap_service, click, debug, event_id)

    # Retrieve the descriptions of the disks of the snapshot:
    snap_disks_service = snap_service.disks_service()
    snap_disks = snap_disks_service.list()

    # Attach disk service
    attachments_service = agent_vm_service.disk_attachments_service()

    attachments = helpers.populateattachments(
        snap_disks, snap, attachments_service, types, logging, click, debug)

    for attach in attachments:
        logging.info(
            '[{}] Attached disk \'{}\' to the agent virtual machine.'.format(
                event_id, attach.disk.id)
        )
        if debug:
            click.echo(
                '[{}] Attached disk \'{}\' to the agent virtual machine.'.format(
                    event_id, attach.disk.id)
            )

    devices = {}
    for i in range(len(attachments)):
        devices[attachments[i].disk.id] = '/dev/backup/' + \
            attachments[i].disk.id

    ONERROR = helpers.qemuconvert(event_id, devices,
                                  vm_backup_absolute + '/', debug, logging, click)

    for attach in attachments:
        attachment_service = attachments_service.attachment_service(attach.id)
        attachment_service.remove()
        logging.info(
            '[{}] Detached disk \'{}\' to from the agent virtual machine.'.format(event_id, attach.disk.id))
        if debug:
            click.echo(
                '[{}] Detached disk \'{}\' to from the agent virtual machine.'.format(
                    event_id, attach.disk.id)
            )
    # Remove the snapshot:
    snap_service.remove()
    logging.info('[{}] Removed the snapshot \'{}\'.'.format(
        event_id, snap.description))
    if debug:
        click.echo('[{}] Removed the snapshot \'{}\'.'.format(
            event_id, snap.description))

    if not unarchive:
        logging.info('[{}] Archiving \'{}\' in \'{}.tar.gz\''.format(
            event_id, vm_backup_absolute, vm_backup_absolute))
        # making archiving
        ONERROR = helpers.make_archive(backup_path, vm_backup_absolute,
                                       debug, event_id, logging)

        if debug:
            click.echo('[{}] Archiving \'{}\' in \'{}.tar.gz\''.format(
                event_id, vm_backup_absolute, vm_backup_absolute))

    if ONERROR == 0:
        shutil.rmtree(vm_backup_absolute)
        message = (
            '[{}] Backup of virtual machine \'{}\' using snapshot \'{}\' is '
            'completed.'.format(event_id, vm.name, Description)
        )
        helpers.send_events(events_service, event_id + 1,
                            types, Description, message, vm)
        logging.info(message)
        if debug:
            click.echo(message)
    else:
        message = (
            '[{}] Backup of virtual machine \'{}\' terminating with return code \'{}\''.format(
                event_id, vm.name, ONERROR)
        )
        helpers.send_events(events_service, event_id + 1,
                            types, Description, message, vm)
        logging.info(message)
        if debug:
            click.echo(message)
    # Finish the connection to the VM Manager
    connection.close()
    logging.info('[{}] Disconnected to the server.'.format(event_id))
    if debug:
        click.echo('[{}] Disconnected to the server.'.format(event_id))
    exit(ONERROR)


@cli.command()
@click.argument('file')
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
    '--api', '-a', envvar='OVIRTURL', required=True, help='url for oVirt API https://manager.example.com/ovirt-engine/api'
)
@click.option(
    '--storage-domain', '-s', envvar='OVIRTSD', required=True, help='Name of oVirt/RHV Storage Domain'
)
@click.option(
    '--cluster', '-C', envvar='OVIRTCLUSTER', required=True, help='Name of oVirt/RHV Cluster'
)
@click.option(
    '--log', '-l', envvar='OVIRTLOG', type=click.Path(), default='/var/log/cli-ovirt-restore.log', show_default=True, help='path log file'
)
@click.option('--debug', '-d', is_flag=True, default=False, help='debug mode')
def restore(username, password, file, ca, api, storage_domain, log, debug, cluster):

    logging.basicConfig(level=logging.DEBUG, format=FORMAT,
                        filename=log)
    connection = sdk.Connection(
        url=api,
        username=username,
        password=password,
        ca_file=ca,
        debug=debug,
        log=logging.getLogger(),
    )
    # oVirt Services API
    #
    #
    #
    #
    # Get the reference to the root of the services tree:
    system_service = connection.system_service()

    # Get the reference to the service that we will use to send events to
    # the audit log:
    events_service = system_service.events_service()
    # Get the reference to the disks services:
    disks_service = system_service.disks_service()
    # Get the reference to the service that manages the virtual machines:
    vms_service = system_service.vms_service()

    vmAgent = helpers.vmobj(vms_service, AgentVM)

    # id for event in virt manager
    event_id = int(time.time())

    logging.info('[{}] Connected to the server.'.format(event_id))
    if debug:
        click.echo('[{}] Connected to the server.'.format(event_id))

    p = Path(file)

    if not p.exists():
        logging.error("[{}] File backup {} not exists".format(
            event_id, p.name))
        exit(1)

    # Get absolute path of restore "file" variable
    tar_file = p.absolute().as_posix()
    # Get full path of parent related to "file" variable
    parent_path = p.absolute().parent.as_posix()

    basedir = tar_file.split('.', 2)[0]
    xml_file = ''

    basedir_obj = Path(basedir)

    vm_name = re.sub(r"\-.*$", '', basedir_obj.name)

    message = (
        '[{}] Restore of virtual machine \'{}\' using file \'{}\' is '
        'starting.'.format(event_id, vm_name, tar_file)
    )

    logging.info(message)
    if debug:
        click.echo(message)

    helpers.send_events(events_service, event_id,
                        types, Description, message)

    if not basedir_obj.exists():
        logging.info("[{}] File {} is compressed".format(event_id, tar_file))
        if debug:
            click.echo("[{}] File {} is compressed".format(event_id, tar_file))
        # Getting name of extracted directory
        logging.info('[{}] Init descompress'.format(event_id))
        if debug:
            click.echo('[{}] Init descompress'.format(event_id))

        ONERROR = helpers.unpack_archive(
            tar_file, parent_path, logging, event_id)

        logging.info('[{}] Finish decompress'.format(event_id))
        if debug:
            click.echo('[{}] Finish decompress'.format(event_id))

    qcow_disks = []

    if basedir_obj.exists():
        for f in basedir_obj.glob('**/*.ovf'):
            xml_file = Path(f).absolute().as_posix()
        logging.info('[{}] Configuration file is [{}]'.format(
            event_id, xml_file))
        if debug:
            click.echo('[{}] Configuration file is [{}]'.format(
                event_id, xml_file))
        for qcow in basedir_obj.glob('**/*.raw'):
            qcow_disks.append(qcow.absolute().as_posix())
    else:
        logging.info('failed to decompress')
        exit(1)

    ovf, ovf_str = helpers.ovf_parse(xml_file)

    disks = []  # disks attachments
    namespace = '{http://schemas.dmtf.org/ovf/envelope/1/}'

    metadata = []
    metas = {}
    elements = ["boot", "volume-format", "diskId",
                "disk-alias", "disk-description", "size", "fileRef", "parentRef"]

    logging.info('[{}] Extracting ovf data'.format(event_id))
    if debug:
        click.echo('[{}] Extracting ovf data'.format(event_id))
    for disk in ovf.iter('Disk'):
        for element in elements:
            if element == 'size':
                metas[str(element)] = int(disk.get(namespace+element)) * 2**30
            elif element == 'fileRef':
                metas[str(element)] = str(
                    disk.get(namespace+element)).split("/")[0]
                metas[str(element)+'_image'] = str(
                    disk.get(namespace+element)).split("/")[1]
            else:
                metas[str(element)] = disk.get(namespace+element)
        metadata.append(metas.copy())

    logging.info('[{}] Defining disks'.format(event_id))
    if debug:
        click.echo('[{}] Defining disks'.format(event_id))
    for meta in metadata:
        if meta["parentRef"]:
            continue
        logging.info('[{}] Defining disk {} with image {} and size {}'.format(
            event_id, meta['fileRef'], meta['fileRef_image'], meta['size']))

        if debug:
            click.echo('[{}] Defining disk {}'.format(
                event_id, meta['fileRef']))
        if meta['volume-format'] == 'COW':
            disk_format = types.DiskFormat.COW
            sparse = True
        else:
            disk_format = types.DiskFormat.RAW
            sparse = False
        if meta['boot']:
            boot = True
        new_disk = disks_service.add(
            disk=types.Disk(
                id=meta['fileRef'],
                name=meta['disk-alias'],
                description=meta['disk-description'],
                format=disk_format,
                provisioned_size=meta['size'],
                storage_domains=[
                    types.StorageDomain(name=storage_domain)
                ],
                bootable=boot,
                image_id=meta['fileRef_image'],
                sparse=sparse
            )
        )

        disk_service = disks_service.disk_service(new_disk.id)
        while disk_service.get().status != types.DiskStatus.OK:
            time.sleep(5)
            logging.info('[{}] Waiting till the disk is created, the satus is \'{}\'.'.format(event_id,
                                                                                              disk_service.get().status))
            if debug:
                click.echo('[{}] Waiting till the disk is created, the satus is \'{}\'.'.format(event_id,
                                                                                                disk_service.get().status))
        disks.append(new_disk)

    # Init copy data process
    # data_vm_service = vms_service.vm_service(vm.id)
    agent_vm_service = vms_service.vm_service(vmAgent.id)
    # Attach disk service
    agent_disks_attachment = agent_vm_service.disk_attachments_service()
    attachments = []
    for disk in disks:
        attach = agent_disks_attachment.add(
            attachment=types.DiskAttachment(
                disk=types.Disk(
                    id=disk.id
                ),
                active=True,
                bootable=False,
                interface=types.DiskInterface.VIRTIO_SCSI,
            ),
        )
        attachments.append(attach)
        logging.info(
            '[{}] Attached disk \'{}\' to the agent virtual machine.'.format(
                event_id, attach.disk.id)
        )
        if debug:
            click.echo(
                '[{}] Attached disk \'{}\' to the agent virtual machine.'.format(
                    event_id, attach.disk.id)
            )

    devices = {}
    for i in range(len(attachments)):
        device = '/dev/backup/' + attachments[i].disk.id
        fileqcow = qcow_disks[i]
        if attachments[i].disk.id in fileqcow:
            devices[fileqcow] = device
        else:
            i -= 1

    for path, device in devices.items():
        logging.info('[{}] Waiting 10s for convert'.format(event_id))
        sleep(10)
        logging.info('[{}] Converting file {}, device {}'.format(
            event_id, path, device))
        ONERROR = helpers.restoredata(device, path, debug)
        if ONERROR != 0:
            logging.error(
                '[{}] Error unpacking file errcode: {}'.format(event_id, ONERROR))

    for attach in attachments:
        attachment_service = agent_disks_attachment.attachment_service(
            attach.id)
        attachment_service.remove()
        logging.info(
            '[{}] Detached disk \'{}\' to from the agent virtual machine.'.format(event_id, attach.disk.id))
        if debug:
            click.echo(
                '[{}] Detached disk \'{}\' to from the agent virtual machine.'.format(
                    event_id, attach.disk.id)
            )
    vm = vms_service.add(
        types.Vm(
            cluster=types.Cluster(
                name=cluster,
            ),
            initialization=types.Initialization(
                configuration=types.Configuration(
                    type=types.ConfigurationType.OVF,
                    data=ovf_str
                )
            ),
        ),
    )

    if ONERROR == 0:
        shutil.rmtree(basedir_obj.absolute().as_posix())
        message = ('[{}] Restore of virtual machine \'{}\' using file \'{}\' is completed.'.format(
            event_id, vm_name, tar_file))
        helpers.send_events(events_service, event_id + 1,
                            types, Description, message)
        logging.info(message)
        if debug:
            click.echo(message)
    else:
        message = ('[{}] Restore of vm: {} terminate with return code \'{}\''.format(
            event_id, vm.name, ONERROR))
        helpers.send_events(events_service, event_id + 1,
                            types, Description, message)
        logging.info(message)
        if debug:
            click.echo(message)
    exit(ONERROR)
