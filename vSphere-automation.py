from urllib3 import exceptions
from warnings import filterwarnings

filterwarnings("ignore", category=DeprecationWarning)
filterwarnings("ignore", category=exceptions.InsecureRequestWarning)

from atexit import register
from getpass import getpass, getuser
from pyVmomi import vim
from requests import get, post

from pyVim.connect import SmartConnect, Disconnect


class Satellite(object):

    host = 'satellite.example.com'
    satellite = 'https://{0}/katello/api/v2'.format(host)

    def __init__(self, username, password, certificate=False):

        self.username = username
        self.password = password
        self.certificate = certificate

        self.Authenticate()

    def Authenticate(self):

        self.Get('https://{0}/api/v2/'.format(self.host))

    def Except(self, array):

        if array.get('error', None):
            raise RuntimeError(array['error']['message'])
        elif array.get('errors', None):
            raise RuntimeError(array['displayMessage'])

        return array

    def Get(self, url):

        return self.Except(get(url, auth=(self.username, self.password), verify=False).json())

    def GetSubscriptions(self):

        self.subscriptions = self.Get('{0}/subscriptions?per_page=10000'.format(self.satellite))
        self.subscriptions['hosts'] = {}

        if not self.subscriptions.get('results', None):
            raise RuntimeError("No subscriptions found, permissions for user '{0}' may be missing".format(self.username))

        for subscription in self.subscriptions['results']:
            if 'host' in subscription:
                self.subscriptions['hosts'][str(subscription['host']['name'][9:-2])] = str(subscription['name'])


class vSphere(object):

    hosts = {
        'portugal': {
            'hostname': 'vcenter-portugal.example.com'},
        'england': {
            'hostname': 'vcenter-england.example.com'}
    }

    def __init__(self, username, password):

        for location in self.hosts:
            self.hosts[location]['object'] = SmartConnect(host=self.hosts[location]['hostname'], user=username, pwd=password, port=443)
            self.hosts[location]['content'] = self.hosts[location]['object'].RetrieveContent()
            register(Disconnect, self.hosts[location]['object'])

    def GetPhysicalHosts(self, location, subscriptions):

        objects = []

        for product in self.hosts[location]['content'].viewManager.CreateContainerView(self.hosts[location]['content'].rootFolder, [vim.HostSystem], True).view:
            if product.name in subscriptions:
                objects.append(product) # product.enterMaintenanceMode()

        return objects

    def GetVirtualMachines(self, location):

        objects = []

        for product in self.hosts[location]['content'].viewManager.CreateContainerView(self.hosts[location]['content'].rootFolder, [vim.VirtualMachine], True).view:
            if 'Red Hat Enterprise Linux' not in product.summary.config.guestFullName and not product.summary.config.template:
                objects.append(product) # product.Relocate(vim.vm.RelocateSpec(host=destination_host), vim.VirtualMachine.MovePriority.defaultPriority)

        return objects
        
    def SetCustomFields(self, location, subscriptions, value):
        
        for field in self.hosts[location]['object'].content.customFieldsManager.field:
            if field.name == 'License':
                break
        else:
            field = self.hosts[location]['object'].content.customFieldsManager.AddFieldDefinition(name='License', moType=vim.HostSystem)
            
        for host in self.GetPhysicalHosts(location, subscriptions):
            self.hosts[location]['object'].content.customFieldsManager.SetField(entity=host, key=field.key, value=value)


username = getuser()
password = getpass()

sat = Satellite(username, password)
api = vSphere(username, password)

sat.GetSubscriptions()

for location in api.hosts.keys():
    api.SetCustomFields(location, sat.subscriptions['hosts'], 'RHEL')
    
    print location.capitalize(), 'Physical Hosts:'
    print ', '.join([each.name for each in api.GetPhysicalHosts(location, sat.subscriptions['hosts'])])

    print location.capitalize(), 'Virtual Machines:'
    print ', '.join([each.name for each in api.GetVirtualMachines(location)]) # each.summary.config.guestFullName
