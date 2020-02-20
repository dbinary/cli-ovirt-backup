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


def send_events(e_service, e_id, types, data_vm, desc):
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
            description=(
                'Backup of virtual machine \'%s\' using snapshot \'%s\' is '
                'starting.' % (data_vm.name, desc)
            ),
        ),
    )


def writeconfig(data_vm):
    """Write XML configuration of vm
    Parameters:
        data_vm: vm object
    """
    ovf_data = data_vm.initialization.configuration.data
    ovf_file = '%s-%s.ovf' % (data_vm.name, data_vm.id)
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
