import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path
from time import sleep

from lxml import etree


def vmobj(vmservice, vm_name):
    """Search for vm by name and return vm object
    Parameters:
        vmservice: vm service object
        vm_name: name of virtual machine to search
    Returns:
        data_vm: object of vm
    """
    data_vm = vmservice.list(
        search='name=%s' % vm_name,
        all_content=True,
    )[0]
    return data_vm


def send_events(e_service, e_id, types, desc, message, data_vm=None):
    """Send events to manager for tasks
    Parameters:
        e_service: service for events
        e_id: id autogenerate
        types: types object from ovirtsdk4
        data_vm: vm object
        desc: description of snapshot
    """
    if data_vm is not None:
        e_service.add(
            event=types.Event(
                vm=types.Vm(
                    id=data_vm.id,
                ),
                origin=desc,
                severity=types.LogSeverity.NORMAL,
                custom_id=e_id,
                description=message,
            ),
        )
    else:
        e_service.add(
            event=types.Event(
                origin=desc,
                severity=types.LogSeverity.NORMAL,
                custom_id=e_id,
                description=message,
            ),
        )


def createdir(path):
    os.makedirs(path)


def writeconfig(data_vm, path):
    """Write XML configuration of vm
    Parameters:
        data_vm: vm object
    """
    ovf_data = data_vm.initialization.configuration.data
    ovf_file = path + '%s-%s.ovf' % (data_vm.name, data_vm.id)
    with open(ovf_file, 'wb') as ovs_fd:
        ovs_fd.write(ovf_data.encode('utf-8'))
    return ovf_file


def createsnapshot(s_service, types, snap_description):
    snap = s_service.add(
        snapshot=types.Snapshot(
            description=snap_description,
            persist_memorystate=False,
        ),
    )
    return snap


def waitingsnapshot(snap, types, logging, time, s_service, clickecho, dbg, e_id):
    while snap.snapshot_status != types.SnapshotStatus.OK:
        logging.info(
            '[{}] Waiting till the snapshot is created, the status is \'{}\'.'.format(e_id, snap.snapshot_status))
        if dbg:
            clickecho.echo('[{}] Waiting till the snapshot is created, the status is \'{}\'.'.format(e_id,
                                                                                                     snap.snapshot_status))
        time.sleep(10)
        snap = s_service.get()
    logging.info('[{}] The snapshot is now complete.'.format(e_id))
    if dbg:
        clickecho.echo('[{}] The snapshot is now complete.'.format(e_id))


def populateattachments(s_disks, snap, a_service, types, logging, clickecho, dbg):
    attachs = []
    for snap_disk in s_disks:
        attachment = a_service.add(
            attachment=types.DiskAttachment(
                disk=types.Disk(
                    id=snap_disk.id,
                    snapshot=types.Snapshot(
                        id=snap.id,
                    ),
                ),
                active=True,
                bootable=False,
                interface=types.DiskInterface.VIRTIO_SCSI,
            ),
        )
        attachs.append(attachment)
    return attachs


def disksattachments(attachments, logging, dbg, clickecho):
    diskarray = []
    for attachment in attachments:
        logging.info('attachment: {}'.format(attachment))
#        logging.info('attachment logicalname: {}'.format(
#            attachment.logicalname))
        logging.info('attachment logical_name: {}'.format(
            attachment.logical_name))
        if attachment.logical_name is not None:
            logging.info(
                'Logical name for disk \'{}\' is \'{}\'.'.format(
                    attachment.disk.id, attachment.logical_name))
            if dbg:
                clickecho.echo(
                    'Logical name for disk \'{}\' is \'{}\'.'.format(
                        attachment.disk.id, attachment.logicalname))
            diskarray.append(attachment)
        else:
            logging.info(
                'Logical name for disk \'{}\'.'.format(
                    attachment.disk.id))
    return diskarray


def getdevices():
    disks = subprocess.check_output(
        'lsblk -do NAME,TYPE |grep disk |grep -v [vsx]da|cut -d" " -f1|xargs', shell=True)
    disks = disks.strip()
    disks = disks.decode()
    disks = disks.split(' ')
    return disks


def converttoqcow2(devices, path, dbg, logging, clickecho):
    for uuid, device in devices.items():
        logging.info('Converting uuid {}, device {}'.format(uuid, device))
        subprocess.call(['qemu-img', 'convert', '-O', 'raw',
                         device, path + uuid + '.raw'])
        if dbg:
            clickecho.echo(
                'Converting uuid {}, device {}'.format(uuid, device))
            subprocess.call(['qemu-img', 'convert', '-p', '-O',
                             'raw', device, path + uuid + '.raw'])


def qemuconvert(event_id, devices, path, dbg, logging, clickecho):
    for uuid, device in devices.items():
        logging.info('[{}] Converting uuid {}, device {}'.format(
            event_id, uuid, device))
        subprocess.call(['qemu-img', 'convert', '-O', 'raw',
                         device, path + uuid + '.raw'])
        if dbg:
            clickecho.echo(
                '[{}] Converting uuid {}, device {}'.format(event_id, uuid, device))
            subprocess.call(['qemu-img', 'convert', '-p', '-O',
                             'raw', device, path + uuid + '.raw'])


def ovf_parse(file):
    with open(file) as f:
        ovf_str = f.read()
        ovf = etree.fromstring(bytes(ovf_str, encoding='utf8'))
    return ovf, ovf_str


def make_archive(workingdir, destination, dbg, e_id, log):
    try:
        os.chdir(workingdir)
        tar_name = destination + '.tar.gz'
        tmp_dir = Path(destination).name
        subprocess.call(['tar', '-czSf', tar_name, tmp_dir])
        if dbg:
            subprocess.call(['tar', '-czvSf', tar_name, tmp_dir])
        shutil.rmtree(destination)
    except (subprocess.SubprocessError, shutil.Error) as e:
        log.error('[{}] Error unpacking file: {}'.format(e_id, e))


def unpack_archive(file, destination, log, e_id):
    try:
        tar = tarfile.open(file)
        tar.extractall(destination)
        tar.close()
    except tarfile.TarError as e:
        log.error('[{}] Error unpacking file: {}'.format(e_id, e))


def converttorestore(e_id, devices, path, dbg, log, clickecho):
    try:
        for uuid, device in devices.items():
            log.info('[{}] Waiting 10s for convert'.format(e_id))
            log.info('[{}] Converting uuid {}, device {}'.format(
                e_id, uuid, device))
            sleep(10)
            subprocess.call(['dd', 'if=' + path, 'of=' +
                             device, 'bs=8M', 'conv=sparse'])
            if dbg:
                clickecho.echo(
                    '[{}] Converting uuid {}, device {}'.format(e_id, uuid, device))
    except subprocess.SubprocessError as e:
        log.error('[{}] Error unpacking file: {}'.format(e_id, e))
        exit(2)
