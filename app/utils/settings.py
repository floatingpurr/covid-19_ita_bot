"""
Just a collection of settings and basic stuff
"""

import pymongo
from . import misc
import os


# data collection and related info
DATA = {
    'nation' : {
        'file_name' : misc.get_env_variable('NATION'),
        'indexes' : [
            pymongo.IndexModel([("data", pymongo.DESCENDING)])
        ],
    }, 
    'regions' : {
        'file_name' : misc.get_env_variable('REGIONS'),
        'indexes' : [
            pymongo.IndexModel([("data", pymongo.DESCENDING), ("variazione_totale_positivi", pymongo.DESCENDING)]),
            pymongo.IndexModel([("denominazione_regione", pymongo.TEXT)]),
        ]
    },
    'provinces' : {
        'file_name' : misc.get_env_variable('PROVINCES'),
        'indexes' : [
            pymongo.IndexModel([("data", pymongo.DESCENDING), ("totale_casi", pymongo.DESCENDING)]),
            pymongo.IndexModel([("denominazione_provincia", pymongo.TEXT)]),
        ]
    }
}

AGGREGATIONS = {
    'week' :{
        'file_name' : None, # not necessary
        'indexes' : [
            pymongo.IndexModel([("_id.area", pymongo.DESCENDING), ("_id.isoYear", pymongo.DESCENDING), ("_id.isoWeek", pymongo.DESCENDING)]),
        ],
    }
}


# Path for downloaded files (in the repository)
DATA_PATH = os.path.dirname(os.path.dirname(__file__))+'/_data/repo/dati-json'


# MongoDB details
MONGO_CLIENT = pymongo.MongoClient('mongodb://mongo:27017/')
MONGO_DB = MONGO_CLIENT.covid19

