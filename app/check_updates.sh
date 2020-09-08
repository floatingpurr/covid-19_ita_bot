#!/bin/bash

REPO_URL=https://github.com/pcm-dpc/COVID-19.git


if [ ! -d _data/repo ]
then
    echo 'Cloning the data repository'
    git clone ${REPO_URL} _data/repo
else
    echo 'Pulling data from the repo'
    git -C _data/repo/ pull
fi

echo 'Running the Python updater'
python refresh.py