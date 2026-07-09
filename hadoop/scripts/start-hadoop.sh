#!/bin/bash

export HDFS_NAMENODE_USER=root
export HDFS_DATANODE_USER=root
export HDFS_SECONDARYNAMENODE_USER=root
export YARN_RESOURCEMANAGER_USER=root
export YARN_NODEMANAGER_USER=root

service ssh start

if [ ! -f /hadoop/dfs/name/current/VERSION ]; then
    echo "Formatting HDFS namenode..."
    hdfs namenode -format -force
fi

echo "Starting HDFS..."
start-dfs.sh

echo "Starting YARN..."
start-yarn.sh

echo ""
echo "============================================"
echo "  Hadoop is running!"
echo "  HDFS Web UI:  http://localhost:9870"
echo "  YARN Web UI:  http://localhost:8088"
echo "  HDFS address: hdfs://localhost:9000"
echo "============================================"
echo ""

# Keep container alive
while true; do sleep 1000; done
