#!/bin/bash

docker build -t asv-simulator:latest -f docker/Dockerfile .

xhost local:root

docker run -it --rm \
  --name asv_sim_dev \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v $(pwd):/workspace/asv-simulator \
  --network host \
  asv-simulator:latest