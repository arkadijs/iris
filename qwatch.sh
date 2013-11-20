#!/bin/sh
while :; do /usr/local/sbin/qwatch.pl 2>&1 | logger -t qwatch -p mail.info; sleep 5; done
