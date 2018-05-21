from urllib3 import exceptions
from warnings import filterwarnings

filterwarnings("ignore", category=DeprecationWarning)
filterwarnings("ignore", category=exceptions.InsecureRequestWarning)

from atexit import register
from getpass import getpass, getuser
from pyVmomi import vim
from requests import get, post

from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask


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


class Windows(object):
    
    hosts = {
        'location1': [
            'windows1.example.com', 'windows2.example.com'], 
        'location1': [
            'windows3.example.com', 'windows4.example.com']
        ]
    }


class vSphere(object):

    hosts = {
        'location1': {
            'hostname': 'location1-vcenter.example.com'},
        'location2': {
            'hostname': 'location1-vcenter.example.com'}
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
            if 'Red Hat Enterprise Linux' in product.summary.config.guestFullName and not product.summary.config.template:
                objects.append(product) # product.Relocate(vim.vm.RelocateSpec(host=destination_host), vim.VirtualMachine.MovePriority.defaultPriority)

        return objects
        
    def FindLocalCluster(self, location, name):
        
        for cluster in self.hosts[location]['object'].content.rootFolder.childEntity[0].hostFolder.childEntity:
            if cluster.name == name:
                return cluster
        else:
            raise RuntimeError("Cluster '{0}' not found in {1}".format(name, self.hosts[location]['hostname'].split('.')[0]))
        
    def SetCustomFields(self, location, subscriptions, value):
        
        for field in self.hosts[location]['object'].content.customFieldsManager.field:
            if field.name == 'License':
                break
        else:
            field = self.hosts[location]['object'].content.customFieldsManager.AddFieldDefinition(name='License', moType=vim.HostSystem)
            
        for host in self.GetPhysicalHosts(location, subscriptions):
            print("Setting 'License' tag as '{1}' for host {0}  in {2}".format(host.name.split('.')[0], value, self.hosts[location]['hostname'].split('.')[0]))
            self.hosts[location]['object'].content.customFieldsManager.SetField(entity=host, key=field.key, value=value)
            
    def CreateAntiAffinityRule(self, cluster):
        
        objects = []
        
        for host in cluster.host: # Change to separate clone machines from running in the same host
            for vm in host.vm:
        #        objects.append(vm)
        
        rule = vim.cluster.AntiAffinityRuleSpec(vm=objects, enabled=True, mandatory=True, name=vm.name[:-2])
        WaitForTask(cluster.ReconfigureEx(vim.cluster.ConfigSpecEx(rulesSpec=[vim.cluster.RuleSpec(info=rule, operation='add')]), modify=True))
        
    def CreateDRSGroup(self, cluster, name, subscriptions):
        
        objects = {'VM': [], 'Host': []}
        
        for host in cluster.host:
            if host.name in subscriptions:
                objects['Host'].append(host)
            for vm in host.vm:
                if 'Red Hat Enterprise Linux' in vm.summary.config.guestFullName and not vm.summary.config.template:
                    objects['VM'].append(vm)
        
        for append in objects.keys():
            group_name = name + '_' + append
            for group in cluster.configurationEx.group:
                if group.name == group_name:
                    operation = "edit"
                    break
            else:
                group = vim.cluster.GroupSpec()
                if append == 'VM':
                    group.info = vim.cluster.VmGroup()
                else:
                    group.info = vim.cluster.HostGroup()
                operation = "add"
            
            spec = vim.cluster.ConfigSpecEx()
            
            setattr(group.info, append.lower(), objects[append])
            group.info.name = group_name
            group.operation = operation
            
            spec.groupSpec.append(group)
            WaitForTask(cluster.ReconfigureComputeResource_Task(spec, True))
            
            print("DRS Group '{0}' {1}ed in {2}".format(group_name, operation, cluster.name))


username = getuser()
password = getpass()

sat = Satellite(username, password)
api = vSphere(username, password)

sat.GetSubscriptions()

for location in api.hosts.keys():
    #api.SetCustomFields(location, sat.subscriptions['hosts'], 'RHEL')
    #api.SetCustomFields(location, Windows.hosts[location], 'Windows')
    #api.CreateAntiAffinityRule(api.FindLocalCluster(location, '{0}ClusterASO_DEV'.format(location[:4].capitalize())))
    api.CreateDRSGroup(api.FindLocalCluster(location, '{0}ClusterASO'.format(location[:4].capitalize())), 'RHEL', sat.subscriptions['hosts'])
    
    #print location.capitalize(), 'Physical Hosts:'
    #print ', '.join([each.name for each in api.GetPhysicalHosts(location, sat.subscriptions['hosts'])])

    #print location.capitalize(), 'Virtual Machines:'
    #print ', '.join([each.name for each in api.GetVirtualMachines(location)]) # each.summary.config.guestFullName
