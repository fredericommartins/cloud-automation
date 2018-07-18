from getpass import getpass, getuser
from socket import error, inet_aton
from subprocess import PIPE, Popen
from textwrap import dedent

from ..vSphere_automation import vSphere


api = vSphere(getuser(), getpass())
stdout, status = Popen('''
for each in `cat hosts | grep -v '^\(\[.*\]$\|#\)' | xargs`; do
    if [[ $each = *"["* ]] && [[ $each = *"]"* ]]; then
        for each in $(eval echo $(sed 's/\[/{/g' <<<${each} | sed 's/]/}/g' | sed 's/:/../g' )); do
            echo $each
        done
    else
        echo $each
    fi
done
''', shell=True, stdout=PIPE, stderr=PIPE).communicate()


for vm in api.GetVirtualMachines(filter=lambda vm: vm.name in stdout):
    for n, nic in enumerate(vm.guest.net):
        addresses = nic.ipConfig.ipAddress

        for address in addresses:
            try:
                inet_aton(address.ipAddress)
            except error:
                pass
            else:
                print('{0}-eth{2}     IN  A  {1}'.format(vm.name, address.ipAddress, n))

    print(dedent('''\
        {0}-oam      IN  CNAME  {0}-eth0
        {0}-srv      IN  CNAME  {0}-eth{1}
        {0}          IN  CNAME  {0}-oam\n'''.format(vm.name, n)))
