#!/bin/sh

yum check-update -y
yum install -y amazon-efs-utils
yum install -y nfs-utils

# makes a directory
mkdir -p /data/packages
mount -t efs fs-d48c7f8c:/ /nextclouddata
