#
# Simple backend demo server image
#

FROM ghcr.io/honzikv/kiv-ds-docker:latest

RUN yum -q -y install python3

COPY src /opt

CMD /usr/bin/python3 /opt/main.py

# EOF
