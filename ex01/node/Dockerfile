FROM ghcr.io/maxotta/kiv-ds-docker:latest
RUN yum -q -y install python3
RUN pip install fastapi uvicorn
COPY src /opt
CMD /usr/bin/python3 /opt/main.py
