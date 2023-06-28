#!/bin/sh
/usr/bin/gunicorn server:app -b 0.0.0.0:3001
