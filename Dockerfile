FROM alpine:3.12

ENV PYTHONUNBUFFERED=1
RUN apk add --update --no-cache python3 && ln -sf python3 /usr/bin/python && apk add bash
RUN python3 -m ensurepip
RUN pip3 install --no-cache --upgrade pip setuptools
RUN pip3 install requests
RUN pip3 install kafka-python
RUN pip3 install pymongo
RUN pip3 install flask
RUN pip3 install kubernetes
RUN apk add graphviz

RUN mkdir -p /home/app

# Add non root user
RUN addgroup -S app && adduser app -S -G app
RUN chown app /home/app

COPY . /home/app
WORKDIR /home/app

USER root

EXPOSE 3001

HEALTHCHECK --interval=3s CMD [ -e /tmp/.lock ] || exit 1

CMD ["./run.sh"]
