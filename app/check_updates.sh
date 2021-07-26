#!/bin/bash

REPO_URL=https://github.com/pcm-dpc/COVID-19.git


if [ ! -d _data/repo ]
then
    echo 'Cloning the data repository'
    git clone ${REPO_URL} _data/repo
else
    echo 'Pulling data from the repo'
    # Ugly workaround to avoid the line endings mismatch
    git -C _data/repo/ fetch
    git -C _data/repo/ reset --hard origin/master
    # Pull new data
    git -C _data/repo/ pull
fi

echo 'Running the Python updater'
python refresh.py