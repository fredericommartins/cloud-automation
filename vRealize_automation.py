#!/usr/bin/env python

from urllib3 import exceptions
from warnings import filterwarnings

filterwarnings("ignore", category=DeprecationWarning)
filterwarnings("ignore", category=exceptions.InsecureRequestWarning)

from nagini import Nagini


api = Nagini(host="vrops.example.com", user_pass=("username", "password"))
print api.get_resources(name='vcenter.example.com', resourceKind="VirtualMachine")
