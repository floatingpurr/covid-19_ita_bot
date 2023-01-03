from collections import OrderedDict
import datetime
import json
import time
from . import settings
from . import misc

from telegram import ReplyKeyboardRemove, ParseMode
from telegram.ext import Updater, PicklePersistence

class Data(object):
    """Basic data class."""


    def __init__(self):
        """create a Data Object and get data"""
        self.data = None


    def md5(self):
        """Calculate the hash of the data directory"""
        return misc.md5(settings.DATA_PATH)


    def get_json_data(self):
        """create and return a dict containing data"""
        self.data = dict()

        for file in settings.DATA.keys():
            with open(settings.DATA_PATH+f'/{settings.DATA[file]["file_name"]}') as f:
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

        # get data status
        meta = self.get_meta()

        # get files md5
        md5 = d.md5()

        try:
            print(meta)
            print(f"md5 from files {md5} // md5 from db {meta['md5']} // equal = {md5 == meta['md5']}")
            
        except:
            print("Cannot get md5 from db (probably it's a first run)")

        # Update just if:
        # - this is the first run (i.e., `not met`  )
        # - or if there are stale data (i.e,. d.md5() != meta['md5'] ) AND there is not another running update (i.e., self.meta['locked']) == True))

        if not meta or md5 != meta['md5']:
            # update report in MongoDB.
            print('updating data...') # Move this print to the logger

            try:
                if meta['locked'] == True:
                    print('Collections are locked')
                    return
            except:
                print("Cannot get locking info (probably it's a first run)")

            # set metadata
            self._set_meta(md5, d.get_date())

            # preprocess data
            data = d.get_json_data()

  
            # save into temporary mongodb collections
            for report in settings.DATA.keys():

                collection = settings.MONGO_DB[f'{report}_temp']

                # drop collection and relative indexes
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

            # Compute weekly aggregates
            self._compute_aggregates()

            # remove lock
            self._unlock_collection()

            print('Data Updatated!')

            days = 15
            data = self.get_national_total_cases(days)

            msg = (
                f"*Aggiornamento dati COVID19 Italia*\n"
                f"*{data[-1]['data']:%a %d %B h.%H:%M}*\n\n"
                f"🇮🇹 *Dati nazionali*:\n"
            )
            from bot import render_data_and_chart # fix circular import, the ugly way
            msg += render_data_and_chart(data = data)

            msg += "\n\n_Digita_ /help _per i dettagli_"

            self.notify_users(msg, aggregation_detail=True)


    def notify_users(self, msg, aggregation_detail=False):
        """Notify Bot Users"""

        # users file
        pp = PicklePersistence(filename='_data/conversationbot')

        updater = Updater(misc.get_env_variable('API_KEY'), persistence=pp)

        # get aggregated national data
        data = self.get_weekly_cases(area="Italia 🇮🇹", limit=10)
        plot = misc.plotify_bar(title=f'Trend nuovi casi per settimana (Italia)', data = data)

        i = 0
        sent = 0
        for i, chat in enumerate(updater.dispatcher.chat_data.keys(), start=1):
            if i != 0 and i % 30 == 0:
                time.sleep(1) # avoids the bot ban :)
            try:
                updater.bot.send_message(chat_id=chat, text=msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())
                if aggregation_detail:
                    updater.bot.send_photo(chat_id=chat, caption=f'Trend settimanale nuovi casi (Italia)', photo=plot, reply_markup=ReplyKeyboardRemove())
                sent += 1
                print(sent) #TODO: remove asap
            except Exception as e:
                print(e)
                pass

        # Send reports
        report = f'{sent} notification(s) sent 👍'
        updater.bot.send_message(chat_id=misc.get_env_variable('DEV'), text=report, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())
        print(report)


    def notify_weekly(self):
        """New cases per week, notification"""
        data = self.get_weekly_summary()

        msg = f'*Aggiornamento settimanale crescita nuovi casi*\n_Settimana: {data["totale"]["settimana_del"]:%d-%b} - {data["totale"]["settimana_fino_al"]:%d-%b}_\n\n'
        icons = misc.get_icons(data["totale"]["delta"], data["totale"]["delta_delta"])
        msg += f'{icons[0]} {icons[1]} *Italia* 🇮🇹\n'

        areas = ['Nord', 'Centro', 'Sud e Isole']

        for area in areas:
            msg += f'\n\n*{area}*:\n'
            regions = data[area]
            for region in regions:
                icons = misc.get_icons(regions[region]["delta"], regions[region]["delta_delta"])
                msg += f'{icons[0]} {icons[1]} {region}\n'

        msg += '\n\n_(Usa il comando /settimanale per esplorare i dettagli)_'
        self.notify_users(msg)


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
            'reportDate' : date,
            'locked' : True,
        })


    def _unlock_collection(self):
        """Release the lock on the collection to allow further updates"""
        settings.MONGO_DB.meta.update_one({}, {"$set": {'locked': False}})

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

    
    def _compute_aggregates(self):
        """ Compute week aggregates """

        print('Computing aggregates...') # Move this print to the logger

        collection = settings.MONGO_DB['week_temp']

        # compute national cases
        settings.MONGO_DB['nation'].aggregate([
                    {
                        "$group":
                        {
                            "_id": { 
                                "area"  : "Italia 🇮🇹",
                                "isoYear": {"$isoWeekYear": "$data" },
                                "isoWeek" : {"$isoWeek": "$data" },
                            
                            },
                            "nuovi_positivi": { "$sum": "$nuovi_positivi" },
                            "giorni": {"$sum": 1},
                            "settimana_del" : {"$min" : "$data"},
                            "settimana_fino_al" : {"$max" : "$data"},
                        }
                    },
                    {"$merge": "week_temp"}
                    ])

        # compute regional cases
        settings.MONGO_DB['regions'].aggregate([
                    {
                        "$group":
                        {
                            "_id": { 
                                "area"  : "$denominazione_regione",
                                "isoYear": {"$isoWeekYear": "$data" },
                                "isoWeek" : {"$isoWeek": "$data" },
                            
                            },
                            "nuovi_positivi": { "$sum": "$nuovi_positivi" },
                            "giorni": {"$sum": 1},
                            "settimana_del" : {"$min" : "$data"},
                            "settimana_fino_al" : {"$max" : "$data"},
                        }
                    },
                    {"$merge": "week_temp"}
                    ])


        # create indexes
        print('Creating indexes...')  # Move this print to the logger
        indexes = settings.AGGREGATIONS['week']['indexes']
        collection.create_indexes(indexes)

        settings.MONGO_DB[f'week_temp'].rename('week', dropTarget=True)



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


    def get_total_cases(self, region=None, offset=None, limit=None):
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

        if offset:
            query.append(
                {'$skip' : offset}
            )

        if limit:
            query.append(
                {'$limit' : limit}
            )


        resultset = settings.MONGO_DB[collection].aggregate(query)
        
        data = list()

        for d in resultset:
            data.append(d)
        return data


    def get_weekly_cases(self, area=None, limit=None, current=True):
        """
        Get weekly cases
        """
        query = [
                    { "$match" : {"_id.area": area}},
                    { "$project" : {"_id" : 0 , "isoYear" : "$_id.isoYear", "isoWeek" : "$_id.isoWeek", "isoWeek" : "$_id.isoWeek", "giorni":1, "nuovi_positivi":1, "settimana_del":1,"settimana_fino_al":1}},
                    { "$sort" : { "isoYear" : -1, "isoWeek": -1} },
                    { "$limit": limit}
                ]

        if not current:
            query[0]["$match"]['giorni'] = {"$eq" : 7} 


        resultset = settings.MONGO_DB["week"].aggregate(query)

        rawData = list(resultset)


        data = []

        for i, d in enumerate(rawData):

            try:
                d['delta'] = d['nuovi_positivi'] - rawData[i + 1]['nuovi_positivi']
                d['delta_delta'] = d['nuovi_positivi'] - 2 * rawData[i + 1]['nuovi_positivi'] + rawData[i + 2]['nuovi_positivi']
            except IndexError:
                pass

            
            data.append(d)
        
        return data


    def get_weekly_summary(self, current=False):
        """
        Get weekly summary
        """
        areas = {
            "Nord" : ["Emilia-Romagna", "Friuli Venezia Giulia", "Liguria", "Lombardia", "P.A. Bolzano", "P.A. Trento", "Piemonte", "Valle d'Aosta", "Veneto",],
            "Centro" : [ "Lazio", "Marche", "Toscana", "Umbria",],
            "Sud e Isole" : [ "Abruzzo", "Basilicata", "Calabria", "Campania", "Molise", "Puglia", "Sardegna", "Sicilia", ]
        }

        data = {}
        
        data['totale'] = self.get_weekly_cases(area='Italia 🇮🇹', limit=3, current=current)[0]

        for area in areas:
            data[area] = OrderedDict()
            for r in areas[area]:
                data[area][r] = self.get_weekly_cases(area=r, limit=3, current=current)[0]
        
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
        for d in settings.MONGO_DB['regions'].find({'data': date}).sort([('totale_positivi',-1)]):
            data.append(d)
        return data