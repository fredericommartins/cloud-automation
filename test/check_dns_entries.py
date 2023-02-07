from getpass import getpass, getuser
from os import system

from ..inventory import hosts
from ..vSphere_automation import vSphere


api = vSphere(getuser(), getpass())

for vm in api.GetVirtualMachines(filter=lambda vm: vm.name in hosts()):
    if system('nslookup {0} &> /dev/null'.format(vm.name)):
        print vm.name, "not in DNS"
    else:
        print vm.name, "in DNS"

    for each in ('srv', 'oam', 'eth0', 'eth1'):
        entry = '{0}-{1}'.format(vm.name, each)
        if system('nslookup {0} &> /dev/null'.format(entry)):
            print entry, "not in DNS"
        else:
            print entry, "in DNS"
    print
