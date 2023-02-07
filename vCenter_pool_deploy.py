#!/usr/bin/env python

__version__ = '1.0a'

import sys
import subprocess

# Install needed python libraries
subprocess.Popen(f"{sys.executable} -m pip install pyvmomi paramiko", shell=True, close_fds=True, 
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

import csv, logging, paramiko, secrets, ssl

from argparse import ArgumentParser, RawDescriptionHelpFormatter
from configparser import ConfigParser
from os import path
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
from textwrap import dedent


class vCenter:
    def __init__(self, parser, name):
        self.host = parser.get(name, 'address')
        self.user = parser.get(name, 'username')
        self.template_name = parser.get(name, 'template_name')
        self.pool_size = int(parser.get(name, 'pool_size'))
        self.api_connect(parser.get(name, 'password'))

    def api_connect(self, password):
        self.si = SmartConnect(host=self.host, user=self.user, pwd=password, sslContext=ssl._create_unverified_context()) # sslContext to be removed in PRD
        self.get_template()

    def get_template(self):
        self.vm = self.search_template([vim.VirtualMachine])
        logging.debug(f"Getting {self.template_name} template specs")
        self.clone_spec = vim.vm.CloneSpec()
        self.clone_spec.location = vim.vm.RelocateSpec()
        self.clone_spec.powerOn = True
        self.clone_spec.template = False

    def clone_template(self, clone_name):
        task = self.vm.Clone(folder=self.vm.parent, name=clone_name, spec=self.clone_spec)
        logging.debug(f"vCenter API: {task}")

    def search_template(self, vimtype):
        container = self.si.content.viewManager.CreateContainerView(self.si.content.rootFolder, 
            vimtype, True)
        for managed_object_ref in container.view:
            if managed_object_ref.name == self.template_name:
                return managed_object_ref
        else:
            raise NameError(f"Template {self.template_name} not found")


class Machine:
    hostname = 'VM-CNRS'
    username = 'cnrsadminuser'
    def __init__(self, n, parser, name):
        self.n = n
        self.hostname += str(n).zfill(2)
        self.ssh_username = parser.get(name, 'username')
        self.ssh_password = parser.get(name, 'password')
        self.password = secrets.token_urlsafe(int(parser.get(name, 'password_length')))
        self.template_address = parser.get(name, 'network_address')
        self.template_interface = parser.get(name, 'network_interface')
        self.template_mask = parser.get(name, 'network_mask')

    def check_address(self):
        p = subprocess.Popen(f"ping -c 2 {self.address}", shell=True, close_fds=True, 
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        p.wait()
        if p.poll():
           return True
        return False

    def configure_machine(self):
        _stdin, stdout, _stderr = self.client.exec_command(
            f'adduser --disabled-password --gecos "" --quiet {self.username}')
        _stdin, stdout, _stderr = self.client.exec_command(
            f'usermod -p $(openssl passwd -1 \'{self.password}\') -a -G sudo {self.username}')
        _stdin, stdout, _stderr = self.client.exec_command(
            f'hostnamectl set-hostname {self.hostname}')
        _stdin, stdout, _stderr = self.client.exec_command(
            f'nmcli con mod "{self.template_interface}" ipv4.addresses {self.address}{self.template_mask}')
        _stdin, stdout, _stderr = self.client.exec_command(
            f'nmcli con up "{self.template_interface}"')
        #_stdin.close(); output = stdout.read(); logging.debug(output)
        self.client.close()

    def get_address(self):
        while True:
            self.address = '.'.join(self.template_address.split('.')[:-1] + [str(self.n)])
            if self.check_address():
                logging.debug(f"No ping response from address {self.address}, using this")
                break
            else:
                if self.n >= int(self.template_address.split('.')[-1]):
                    raise RuntimeError("No more addresses to check")
                logging.debug(f"Address {self.address} already in use, trying next one")
                self.n += 1

    def ssh_connect(self):
        self.client = paramiko.client.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        while True:
            try:
                self.client.connect(self.template_address, username=self.ssh_username, password=self.ssh_password)
            except paramiko.ssh_exception.NoValidConnectionsError:
                logging.debug("Cloned VM not yet SSH accessible")
            else:
                break
        
    def ssh_disconnect(self):
        self.client.close()


def ArgsParser():
    parser = ArgumentParser(prog='python {0}'.format(path.basename(__file__)), add_help=False,
        formatter_class=RawDescriptionHelpFormatter, description=dedent('''\
            vCenter API Pool Deploy
            -----------------------
              Python script for
              vCenter template
              deploy.
            '''), epilog = dedent('''\
            Check the git repository at https://github.com/fredericommartins/cloud-automation,
            for more information about usage, documentation and bug report.'''))
    mandatory = parser.add_argument_group('Mandatory')
    mandatory.add_argument('-i', '--ini', metavar='file', type=str, help="Configuration file .ini path", required=True)
    optional = parser.add_argument_group('Optional')
    optional.add_argument('-d', '--debug', action='store_true', help="Run script in debug mode")
    optional.add_argument('-h', '--help', action='help', help="Show this help message")
    optional.add_argument('-v', '--version', action='version', version='{0} {1}'.format(path.basename(__file__), __version__),
        help='Show program version')
    return parser.parse_args()


args = ArgsParser()
conf = ConfigParser()
conf.read(args.ini)
logging.basicConfig(stream=sys.stdout, encoding='utf-8', level=logging.DEBUG if args.debug else logging.INFO, # filename='/path/to/logfile)'
  format='%(asctime)s %(levelname)s %(message)s')
api = vCenter(conf, 'vcenter')
logging.info(f"Connected to vCenter API on {api.host}")

for n in range(1, api.pool_size+1):
    vm = Machine(n, conf, 'template')
    logging.info(f"Clonning '{vm.hostname}' from template '{api.template_name}'")
    api.clone_template(vm.hostname)
    vm.get_address()
    vm.ssh_connect()
    logging.info(f"Configuring VM '{vm.hostname}'")
    vm.configure_machine()
    vm.ssh_disconnect()

    with open('vcenter_pool.csv', 'a', newline='') as csvfile:
        poolwriter = csv.writer(csvfile, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        poolwriter.writerow([vm.hostname, vm.address, vm.username, vm.password])

Disconnect()
