import os
import shutil
import json
from pathlib import Path
from subprocess import check_output, call


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


def send_events(e_service, e_id, types, data_vm=None, desc, message):
    """Send events to manager for tasks
    Parameters:
        e_service: service for events
        e_id: id autogenerate
        types: types object from ovirtsdk4
        data_vm: vm object
        desc: description of snapshot
    """
    if data_vm:
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


def waitingsnapshot(snap, types, logging, time, s_service, clickecho, dbg):
    while snap.snapshot_status != types.SnapshotStatus.OK:
        logging.info(
            'Waiting till the snapshot is created, the satus is \'{}\'.'.format(snap.snapshot_status))
        if dbg:
            clickecho.echo('Waiting till the snapshot is created, the satus is \'{}\'.'.format(
                snap.snapshot_status))
        time.sleep(10)
        snap = s_service.get()
    logging.info('The snapshot is now complete.')
    if dbg:
        clickecho.echo('The snapshot is now complete.')


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
                interface=types.DiskInterface.VIRTIO,
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
    disks = check_output(
        'lsblk -do NAME,TYPE |grep disk |grep -v [vsx]da|cut -d" " -f1|xargs', shell=True)
    disks = disks.strip()
    disks = disks.decode()
    disks = disks.split(' ')
    return disks


def converttoqcow2(devices, path, dbg, logging, clickecho):
    for uuid, device in devices.items():
        logging.info('Converting uuid {}, device {}'.format(uuid, device))
        call(['qemu-img', 'convert', '-f', 'raw', '-O',
              'qcow2', device, path + uuid + '.qcow2'])
        if dbg:
            clickecho.echo(
                'Converting uuid {}, device {}'.format(uuid, device))
            call(['qemu-img', 'convert', '-p', '-f', 'raw', '-O',
                  'qcow2', device, path + uuid + '.qcow2'])


def getinfoqcow2(file, restore_path, clickecho):
    disks_info = []
    clickecho.echo('Iniciando...')
    if file.endswith('.gz'):
        clickecho.echo('Iniciando desempaquetado')
        shutil.unpack_archive(file, restore_path, 'gztar')
        tarfile = Path(file).stem
        f_path = Path(tarfile).stem
        clickecho.echo('{}'.format(f_path))
        clickecho.echo('Desempaquetado terminado')
    else:
        f_path = file

    disks = Path(f_path).glob('**/*.qcow2')
    for disk in disks:
        clickecho.echo('Ejecutando qemu-img')
        output = check_output(
            'qemu-img info --output json ' + str(disk), shell=True).decode(encoding='UTF-8')
        py_object = json.loads(output)
        disks_info.append(py_object)
    return disks_info, f_path


def ovf_parse(file):
    with open(file) as f:
        ovf_str = f.read()

        ovf = etree.fromstring(bytes(ovf_str, encoding='utf8'))
    return ovf, ovf_str
