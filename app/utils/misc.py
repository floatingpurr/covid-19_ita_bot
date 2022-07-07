# -*- coding: utf-8 -*-
"""
Collection of utils
"""

import os
import gc
import requests
import json
import hashlib
import dateparser
from ascii_graph import Pyasciigraph
import matplotlib.pyplot as plt
import numpy as np
import io
import locale



locale.setlocale(locale.LC_ALL, "it_IT.UTF-8")



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

    # ugly way to avoid circular imports
    from . import settings

    files = [ 
        settings.DATA['nation']['file_name'],
        settings.DATA['regions']['file_name'],
        settings.DATA['provinces']['file_name'],
        ]

    hash_md5 = hashlib.md5()
    for f in files:
        with open(dir+'/'+f, "rb") as f:
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


def chartify(title, data, auto=False):
    """Create an ascii chart passing a list of tuples [('label', int)]"""

    if auto == True:

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

    # if we get there, then use manual mode

    chart = title + '\n'
    chart += '-'*30 + '\n'

    max_value = max(count for _, count in data)
    min_value = min(count for _, count in data)
    increment = (max_value - min_value) / 12

    for label, count in data:

        bar_chunks, remainder = divmod(int((count - min_value) * 8 / increment), 8)

        # Main width
        bar = '█' * bar_chunks

        # Fractional part
        if remainder > 0:
            bar += chr(ord('█') + (8 - remainder))

        # If the bar is empty, add a left one-eighth block
        bar = bar or '▏'

        chart += f'{count:>7n} {bar:<13} | {label:>6}\n'

    return chart


def plotify(title, data, key):
    """Return a line chart (in raw bytes)"""

    color_map = {
        'totale_positivi' : 'mediumvioletred',
        'totale_casi' : 'orangered'
    }

    # create a new figure
    plt.figure()

    dates = list()
    values = list()

    for d in data:
        dates.append(f"{d['data']:%d-%b}")
        values.append(int(d[key]))



    # Add title and axes names
    plt.title(title)
    # plt.xlabel('data')
    # plt.ylabel(key)


    plt.plot(dates, values, marker='o', color=color_map[key], linewidth=3)
    plt.xticks(rotation=45)
    bottom, top = plt.ylim()
    plt.ylim(bottom=bottom, top=top)
    plt.grid()
    
    # prettify y values
    current_values = plt.gca().get_yticks()
    plt.gca().set_yticklabels(['{:n}'.format(int(x)) for x in current_values])

    # responsive layout
    plt.tight_layout()


    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)

    ### Release memory
    # Clear the current axes.
    plt.cla() 
    # Clear the current figure.
    plt.clf() 
    # Closes all the figure windows.
    plt.close('all')   
    # plt.close(fig)
    gc.collect()

    return buf

def plotify_bar(title, data):
    """Return a bar chart (in raw bytes)"""

    x, y, z, labels = [], [], [], []

    for d in reversed(data[:len(data) - 1]):
        x.append(f"{d['settimana_del']:%d-%b}\n{d['settimana_fino_al']:%d-%b}")
        y.append(d['nuovi_positivi'])
        z.append("lightgrey" if d['giorni'] < 7 else 'green' if d['delta'] <= 0 else 'red' )
        labels.append(human_format(d['nuovi_positivi']) if d['giorni'] == 7 else f"{human_format(d['nuovi_positivi'])}\n(in corso)" )

    x_pos = np.arange(len(x))

    # create a new figure
    plt.figure()

    plt.title(title)

    # Create bars with different colors
    plt.bar(x_pos, y, color=z)

    # Create names on the x-axis
    plt.xticks(x_pos, x, rotation=40)


    # Text on the top of each bar
    x_ticks = plt.gca().get_xticks()
    for i in range(len(y)):
        text = data[i]
        plt.text(x = x_ticks[i], y = y[i]+5, s = labels[i], size = 9, horizontalalignment='center', verticalalignment='bottom')

    # prettify y values
    current_values = plt.gca().get_yticks()
    plt.gca().set_yticklabels(['{:n}'.format(int(x)) for x in current_values])

    # responsive layout
    plt.tight_layout()



    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)

    ### Release memory
    # Clear the current axes.
    plt.cla() 
    # Clear the current figure.
    plt.clf() 
    # Closes all the figure windows.
    plt.close('all')   
    # plt.close(fig)
    gc.collect()

    return buf


def human_format(num, signed=False):
    """
    Return a number in a human readable format
    see: https://stackoverflow.com/a/45846841
    """
    if num <= 1005:
        return num

    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    my_num = '{} {}'.format('{:f}'.format(num).rstrip('0').rstrip('.').replace('.',','), ['', 'mila', 'Mln.', 'G', 'T'][magnitude])
    if signed and num > 0:
        my_num = '+' + my_num
    return my_num


def get_icons(delta, delta_delta):
    """return icons according to the variaiton and to the variation of the variation"""

    if delta > 0:
        if delta_delta > 0:
            return ('🔴', '⬆️')
        
        if delta_delta == 0:
            return ('🔴', '➡️')
        
        if delta_delta < 0:
            return ('🔴', '↗️')


    if delta <= 0:
        if delta_delta > 0:
            return ('🟢', '↘️')

        if delta_delta == 0:
            return ('🟢', '➡️')
        
        if delta_delta < 0:
            return ('🟢', '⬇️')
