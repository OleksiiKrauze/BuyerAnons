#!/bin/bash
# Wrapper to capture Docker output
cd "D:/1. Projects/BuyerAnons"
docker-compose run --rm -T buyer-anons "$@" 2>&1 | tee /tmp/docker_output.txt
