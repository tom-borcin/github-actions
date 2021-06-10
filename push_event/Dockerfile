FROM node:current-buster-slim

LABEL "com.github.actions.name"="Check push event"
LABEL "com.github.actions.description"="Check push event for cherry-picked pull requests"
LABEL "com.github.actions.icon"="fast-forward"
LABEL "com.github.actions.color"="green"

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8

ADD requirements.txt /tmp/requirements.txt

RUN apt-get update && apt-get install -y python3-pip && pip3 install -r /tmp/requirements.txt

RUN rm /tmp/requirements.txt

RUN npm i -g @shogobg/markdown2confluence@0.1.0

ADD push_event.py /push_event.py
ADD util.py ../utilities/util.py

ENTRYPOINT ["/usr/bin/python3", "/push_event.py"]
