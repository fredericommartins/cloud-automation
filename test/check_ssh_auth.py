#!/usr/bin/env python

import sys
import subprocess

# Install needed python libraries
subprocess.Popen(f"{sys.executable} -m pip install paramiko", shell=True, close_fds=True,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

import csv, paramiko
from configparser import ConfigParser

parser = ConfigParser(); parser.read('../file.ini')
client = paramiko.client.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

with open('vcenter_pool.csv', 'r', newline='') as csvfile:
    csvreader = csv.reader(csvfile, delimiter=' ')
    for row in csvreader:
        print(f"Testing {row[0]} SSH authentication")
        try:
            client.connect(row[1], username=row[2], password=row[3])
        except paramiko.ssh_exception.AuthenticationException:
            print(f"SSH authentication failed for {row[0]} ({row[1]}), with user {row[2]} with password {row[3]}")

