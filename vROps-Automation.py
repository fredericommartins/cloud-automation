#!/usr/bin/env python

from urllib3 import exceptions
from warnings import filterwarnings

filterwarnings("ignore", category=DeprecationWarning)
filterwarnings("ignore", category=exceptions.InsecureRequestWarning)

from nagini import Nagini


api = Nagini(host="vrops-hostname.fqdn", user_pass=("username", "password"))
print api.get_resources(name='vcenter-hostname', resourceKind="VirtualMachine")
