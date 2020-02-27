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


def send_events(e_service, e_id, types, data_vm, desc, message):
    """Send events to manager for tasks
    Parameters:
        e_service: service for events
        e_id: id autogenerate
        types: types object from ovirtsdk4
        data_vm: vm object
        desc: description of snapshot
    """
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


def createdir(path):
    import os
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
    from subprocess import check_output

    disks = check_output(
        'lsblk -do NAME,TYPE |grep disk |grep -v [vs]da|cut -d" " -f1|xargs', shell=True)
    disks = disks.strip()
    disks = disks.decode()
    disks = disks.split(' ')
    return disks


def converttoqcow2(devices, path, dbg):
    from subprocess import call

    for uuid, device in devices.items():
        call(['qemu-img', 'convert', '-f', 'raw', '-O',
              'qcow2', device, path + uuid + '.qcow2'])
        if dbg:
            call(['qemu-img', 'convert', '-p', '-f', 'raw', '-O',
                  'qcow2', device, path + uuid + '.qcow2'])
