import datetime
import json
from . import settings
from . import misc


class Data(object):
    """Basic data class."""


    def __init__(self):
        """create a Data Object and get data"""
        self._fetch_data()
        self.data = None


    def _fetch_data(self):
        """Fetch and save official data into files"""

        print('dowloading data...') # Move this print to the logger
        for file in settings.DATA.keys():
            misc.save_data(settings.DATA[file]['url'], settings.DATA_PATH+f'{file}.json')


    def md5(self):
        """Calculate the hash of the data directory"""
        return misc.md5(settings.DATA_PATH)


    def get_json_data(self):
        """create and return a dict containing data"""
        self.data = dict()

        for file in settings.DATA.keys():
            with open(settings.DATA_PATH+f'{file}.json') as f:
                self.data[file] = json.load(f, object_hook=misc.json_dates_hook)
        return self.data


    def get_date(self):
        """
        Return report date
        i.e., the last value of `data` in one of the file
        """

        # retrieve data if necessary
        if not self.data: 
            self.get_json_data()
        return self.data['nation'][-1]['data']






class Report(object):
    """The report class."""


    def refresh(self):
        """download new data and save into mongo if they are fresher"""
        d = Data()

        if not self.get_meta() or d.md5() != self.get_meta()['md5']:
            # update report in MongoDB.
            print('updating data...') # Move this print to the logger

            # set metadata
            self._set_meta(d.md5(), d.get_date())

            # preprocess data
            data = d.get_json_data()

  
            # save into temporary mongodb collections
            for report in settings.DATA.keys():

                collection = settings.MONGO_DB[f'{report}_temp']

                # drop collection an relative indexes
                collection.drop()

                # update data
                collection.insert_many(data[report])

                # create indexes
                print('Creating indexes...')  # Move this print to the logger
                indexes = settings.DATA[report]['indexes']
                collection.create_indexes(indexes)

            # rename temporary collections
            for report in settings.DATA.keys():
                print('Renaming collections...')  # Move this print to the logger
                settings.MONGO_DB[f'{report}_temp'].rename(report, dropTarget=True)

            # set keyboards options according to new values
            self._set_keyboards()
           

            
    def get_meta(self):
        """Get report Metadata"""
        return settings.MONGO_DB.meta.find_one()


    def _set_meta(self, md5, date):
        """Set report metadata"""

        # drop the meta collection
        settings.MONGO_DB.meta.drop()

        # insert new meta
        settings.MONGO_DB.meta.insert_one({
            'timestamp' : datetime.datetime.now(),
            'md5' : md5,
            'reportDate' :date,
        })
        

    def get_keyboard(self, keyboard_name):
        """Return a list of keyboard options according to its name"""
        try:
            return settings.MONGO_DB['keyboards'].find_one({"keyboard_name" : keyboard_name})['values']
        except TypeError: # no match with keyboard_name
            return None


    def _set_keyboards(self):
        """Set keyboards values (distinct values for queries)"""

        print('Setting keyboards...') # Move this print to the logger

        # drop existing collection
        settings.MONGO_DB['keyboards'].drop()

        # setting regions keyboard
        values = settings.MONGO_DB['regions'].distinct('denominazione_regione')

        # sort values before storing
        values.sort()

        settings.MONGO_DB['keyboards'].insert_one({
            'keyboard_name' : 'italy',
            'values' : values
        })

        # setting provinces keyboards
        provs_per_reg = settings.MONGO_DB['provinces'].aggregate([{"$group": { "_id": { 'denominazione_regione': "$denominazione_regione", 'denominazione_provincia': "$denominazione_provincia" } } }])

        provinces_keyboards = []

        for item in provs_per_reg:
            reg = item['_id']['denominazione_regione']
            prov = item['_id']['denominazione_provincia']

            # check if the keyboard is already in the list and update values accordingly
            r = next((region for region in provinces_keyboards if region['keyboard_name'] == reg), None)
            if r:
                r['values'].append(prov)
            else:
                provinces_keyboards.append({
                    'keyboard_name' : reg,
                    'values' : [prov]
                })

        # sort data
        for item in provinces_keyboards:
            item['values'].sort()

        # add to mongo
        settings.MONGO_DB['keyboards'].insert_many(provinces_keyboards)

        # create the index on keyboard name
        settings.MONGO_DB['keyboards'].create_index('keyboard_name')


    def get_national_total_cases(self, days):
        """ Get national cases of last `days` """
        data = list()
        for d in settings.MONGO_DB['nation'].find().sort([('data',-1)]).limit(days):
            data.append(d)
        data.reverse()
        return data


    def get_region_cases(self, region, days):
        """ Get cases of a `region` of last `days` """
        data = list()
        for d in settings.MONGO_DB['regions'].find({'denominazione_regione': region}).sort([('data',-1)]).limit(days):
            data.append(d)
        data.reverse()
        return data


    def get_total_cases(self, region=None, limit=None):
        """
        Get today's total cases and differentials:
        - region=None      for all the regions
        - region='all'     for all the provinces
        - region='foo'     for all the provinces of the region foo
        
        Use `limit` to limit the resultset
        """

        #TODO: use the aggreagation framework instead
        date = self.get_meta()['reportDate']


        yesterday = date - datetime.timedelta(days=1)
        # lower bound date for the query (i.e., from yesterday at midnight)
        yesterday = datetime.datetime.strptime(f'{yesterday.date()}', '%Y-%m-%d')


        query = [{ 
                    "$match" : { 
                        # "denominazione_regione" : region
                        "data" : {
                            "$gte" : yesterday
                        }
                    }
                },
                {
                    "$sort": { 
                        "data" : 1 
                    } 
                },
                {
                    "$group": {
                        "data": {
                            "$last": "$data"
                        },
                        "yesterday": {
                            "$first": "$totale_casi"
                        },
                        "today": {
                            "$last": "$totale_casi"
                        },
                    }
                },
                { 
                    "$project": {
                        "_id": 1,
                        "data" : 1,
                        "totale_casi" : "$today",
                        "diff": { "$subtract": [ "$today", "$yesterday" ] },
                    }
                },
                {
                    "$sort": { 
                        "diff" : -1 
                    } 
                },
        ]

        # customize query
        if region == None:
            # get regional data
            collection = 'regions'
            query[2]['$group']['_id'] = "$denominazione_regione"
        elif region == 'all':
            # all the provinces
            collection = 'provinces'
            # remove In fase di definizione/aggiornamento from this output
            query[0]['$match']["denominazione_provincia"] = {'$ne' : 'In fase di definizione/aggiornamento'}
            query[2]['$group']['_id'] = "$denominazione_provincia"
        else:
            # get provinces data for a region
            collection = 'provinces'
            query[0]['$match']["denominazione_regione"] = region
            query[2]['$group']['_id'] = "$denominazione_provincia"

        if limit:
            query.append(
                {'$limit' : limit}
            )


        resultset = settings.MONGO_DB[collection].aggregate(query)
        
        data = list()

        for d in resultset:
            data.append(d)
        return data


    def get_province_cases(self, province, days):
        """ Get cases of a `province` of last `days` """
        data = list()
        for d in settings.MONGO_DB['provinces'].find({'denominazione_provincia': province}).sort([('data',-1)]).limit(days):
            data.append(d)
        data.reverse()
        return data


    def get_regional_positive_cases(self):
        """Rank new cases per region"""
        #TODO: use the aggreagation framework instead
        date = self.get_meta()['reportDate']
        data = list()
        for d in settings.MONGO_DB['regions'].find({'data': date}).sort([('totale_attualmente_positivi',-1)]):
            data.append(d)
        return data
