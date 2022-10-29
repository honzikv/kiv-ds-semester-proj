FROM ghcr.io/maxotta/kiv-ds-docker:latest
RUN yum -q -y install python3
RUN yum install make gcc wget openssl-devel bzip2-devel libffi-devel zlib-devel -y
WORKDIR /opt
RUN wget https://www.python.org/ftp/python/3.9.6/Python-3.9.6.tgz
RUN tar -xzf Python-3.9.6.tgz
WORKDIR /opt/Python-3.9.6
RUN ./configure --enable-optimizations
RUN make altinstall
RUN rm -f /opt/Python-3.9.6.tgz
RUN pip3.9 install requests
RUN pip3.9 install fastapi
RUN pip3.9 install uvicorn
WORKDIR /
COPY src /opt
CMD python3.9 /opt/api.py
