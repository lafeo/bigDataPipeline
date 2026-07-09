FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    openjdk-11-jdk \
    python3 \
    python3-pip \
    wget \
    ssh \
    rsync \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-arm64
# Fallback: detect actual Java path at build time
RUN if [ ! -d "$JAVA_HOME" ]; then export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java)))); fi
ENV HADOOP_VERSION=3.3.6
ENV HADOOP_HOME=/opt/hadoop
ENV HADOOP_CONF_DIR=$HADOOP_HOME/etc/hadoop
ENV PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin

RUN wget -q https://archive.apache.org/dist/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz \
    && tar -xzf hadoop-${HADOOP_VERSION}.tar.gz -C /opt/ \
    && mv /opt/hadoop-${HADOOP_VERSION} ${HADOOP_HOME} \
    && rm hadoop-${HADOOP_VERSION}.tar.gz

RUN ssh-keygen -t rsa -P '' -f ~/.ssh/id_rsa \
    && cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys \
    && chmod 0600 ~/.ssh/authorized_keys

RUN echo "export JAVA_HOME=${JAVA_HOME}" >> ${HADOOP_CONF_DIR}/hadoop-env.sh

COPY config/core-site.xml ${HADOOP_CONF_DIR}/core-site.xml
COPY config/hdfs-site.xml ${HADOOP_CONF_DIR}/hdfs-site.xml
COPY config/mapred-site.xml ${HADOOP_CONF_DIR}/mapred-site.xml
COPY config/yarn-site.xml ${HADOOP_CONF_DIR}/yarn-site.xml

RUN mkdir -p /hadoop/dfs/name /hadoop/dfs/data

COPY scripts/start-hadoop.sh /start-hadoop.sh
RUN chmod +x /start-hadoop.sh

WORKDIR /data

EXPOSE 9870 8088 9000

CMD ["/start-hadoop.sh"]
