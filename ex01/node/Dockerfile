FROM ghcr.io/maxotta/kiv-ds-docker:latest
RUN yum -q -y install python3
RUN pip3 install requests
RUN pip3 install fastapi
RUN pip3 install uvicorn
COPY src /opt
CMD /usr/bin/python3 /opt/api.py
