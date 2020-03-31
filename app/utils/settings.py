"""
Just a collection of settings and basic stuff
"""

import pymongo
from . import misc
import os


# data collection and related info
DATA = {
    'nation' : {
        'url' : misc.get_env_variable('NATION'),
        'indexes' : [
            pymongo.IndexModel([("data", pymongo.DESCENDING)])
        ],
    }, 
    'regions' : {
        'url' : misc.get_env_variable('REGIONS'),
        'indexes' : [
            pymongo.IndexModel([("data", pymongo.DESCENDING), ("variazione_totale_positivi", pymongo.DESCENDING)]),
            pymongo.IndexModel([("denominazione_regione", pymongo.TEXT)]),
        ]
    },
    'provinces' : {
        'url' : misc.get_env_variable('PROVINCES'),
        'indexes' : [
            pymongo.IndexModel([("data", pymongo.DESCENDING), ("totale_casi", pymongo.DESCENDING)]),
            pymongo.IndexModel([("denominazione_provincia", pymongo.TEXT)]),
        ]
    }
}


# Path for downloaded files
DATA_PATH = os.path.dirname(os.path.dirname(__file__))+'/_data/'


# MongoDB details
MONGO_CLIENT = pymongo.MongoClient('mongodb://mongo:27017/')
MONGO_DB = MONGO_CLIENT.covid19

