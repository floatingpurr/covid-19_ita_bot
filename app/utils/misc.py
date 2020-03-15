"""
Collection of utils
"""

import os
import requests
import json
import hashlib
import dateparser
from ascii_graph import Pyasciigraph



def get_env_variable(var_name):
    """Get the environment variable or return an exception."""
    try:
        return os.environ[var_name]
    except KeyError:
        error_msg = "Set the {} environment variable".format(var_name)

    raise Exception(error_msg)


def get_json_data(url):
    """Return a dict parsing a remote json file"""

    r = requests.get(url)
    try:
        return r.json()
    except json.JSONDecodeError:
        # Catch the Unexpected UTF-8 BOM error
        r.encoding='utf-8-sig'
        return r.json()



def save_data(url, file):
    """Save a dict into a file"""
    with open(file, 'w') as f:
        json.dump(get_json_data(url), f)


def md5(dir):
    """get the MD5 checksum of files in a dir reading chunks of 4096 bytes"""

    files = [f for f in os.listdir(dir) if os.path.isfile(os.path.join(dir, f))]

    hash_md5 = hashlib.md5()
    for f in files:
        with open(dir+f, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
                    
    return hash_md5.hexdigest()


def json_dates_hook(dict):
    """Transform a serialized `data` into a datetime"""
    try:
        dict['data'] = dateparser.parse(dict['data'])
        return dict
    except KeyError:
        return dict


def chartify(title, data):
    """Create an ascii chart passing a list of tuples [('label', int)]"""
    chart = ''
    
    graph = Pyasciigraph(
        line_length=8,
        min_graph_length=15,
        separator_length=2,
        titlebar='-',
        float_format='{0:.0f}'
        )
    
    for line in  graph.graph(title, data):
        chart += line+'\n'
    
    return chart
