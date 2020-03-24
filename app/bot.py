#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import locale
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, ParseMode
from telegram.ext import Updater, CommandHandler, ConversationHandler, MessageHandler, Filters

from utils import misc
from utils.report import Report


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# set locale
locale.setlocale(locale.LC_ALL, "it_IT.UTF-8")


REGION, PROVINCE = range(2)

COMMANDS = (
    "/italia - Dati aggregati a livello nazionale\n"
    "/nuovi - Incremento dei casi attualmente positivi\n"
    "/regione - Dati per regione\n"
    "/provincia - Dati per provincia\n"
    "/help - Istruzioni sull’utilizzo\n"
    "/credits - Informazioni su questo bot\n\n"
)

# the main report object
R = Report()

def get_keyboard(keyboard_name):
    """get an generate a keyboard using stored data"""

    # Build the keyboard dynamically
    data_kb = R.get_keyboard(keyboard_name)

    if not data_kb:
        return None

    keyboard = []
    i = 0
    for option in data_kb:
        line, remainder = divmod(i, 2)
        # display two keys per line
        if remainder == 0:
            # create new line
            keyboard.append([])
        keyboard[line].append(option)
        i += 1
    return keyboard


def plot_cases(title, data, key):
    """Plot trend of cases using a `key`"""
    ts = list()
    for d in data:
        ts.append(
            (
                f"{d['data']:%d-%b}", 
                int(d[key])
            )
        )
    
    return misc.chartify(title, ts)


def render_data_and_chart(data):
    """Return the message `msg` + the chart to render for national and regional data"""

    msg = ''
    today = data[-1]
    yesterday = data[-2]

    outline = {
        'Positivi' : {
            'today' : today['totale_attualmente_positivi'],
            'diff'  : today['nuovi_attualmente_positivi']
        },
        'Guariti' : {
            'today' : today['dimessi_guariti'],
            'diff'  : today['dimessi_guariti'] - yesterday['dimessi_guariti']
        },
       'Deceduti' : {
            'today' : today['deceduti'],
            'diff'  : today['deceduti'] - yesterday['deceduti']
        },
        'Tot. Casi' : {
            'today' : today['totale_casi'],
            'diff'  : today['totale_casi'] - yesterday['totale_casi']
        },
    }

    for o in outline:
        t = outline[o]['today']
        d = outline[o]['diff']
        if o == 'Tot. Casi':
            msg += f"\n`_____________________________`"
        msg += f"\n`{o:>11}: {t:>7n} ({f'{d:+n}':>6})`"
    
    chart = plot_cases(f'Trend ultimi {len(data)} giorni', data, 'totale_attualmente_positivi')
    msg += f'\n\n\n\n*Attualmente positivi*\n`{chart}`'
    return msg



def start(update, context):
    """Getting started with this bot"""
    logger.info(f"User {update.message.from_user} started the bot")
    
    msg = (
        "*Dati aggiornati dei casi di COVID-19 in Italia*\n\n"
        "_Dati e comandi disponibili_:\n\n"
        f"{COMMANDS}"

   
        "I [dati usati da questo bot](https://github.com/pcm-dpc/COVID-19) sono rilasciati soltanto a fini informativi. Gli aggiornamenti vengono aggiornati dalla Protezione Civile ogni giorno attorno alle ore 18:00.\n\n*#restiamoacasa*\n*#tuttoandràbene* 🌈"
    )

    # use ReplyKeyboardRemove() to clear stale keys
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN,reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)


def nation(update, context):
    """Render national data"""
    logger.info(f"User {update.message.from_user} requested national data")
    days = 7
    data = R.get_total_cases(days)

    msg = (
        f"*Dati nazionali*\n\n"
        f"Aggiornamento: *{data[-1]['data']:%a %d %B h.%H:%M}*\n"
    )

    msg += render_data_and_chart(data)

    # use ReplyKeyboardRemove() to clear stale keys
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())


def new_cases_per_region(update, context):
    """Today's cases per region"""
    logger.info(f"User {update.message.from_user} requested the ranking")
    data = R.get_ranking()

    if not data:
        # exit and use ReplyKeyboardRemove() to clear stale keys
        update.message.reply_text('Nessun dato disponibile', reply_markup=ReplyKeyboardRemove())

    msg = (
        f"Incremento degli *attualmente positivi*\n(_per regione_)\n\n"
        f"Aggiornamento: *{data[0]['data']:%a %d %B h.%H:%M}*\n" # take the date from the first returned doc
    )

    # build chart
    ts = list()
    for d in data:
        region = d['denominazione_regione'][:16] + (d['denominazione_regione'][16:] and '.')
        n = d["nuovi_attualmente_positivi"]
        msg +=f"`\n {region:>19} {f'{n:+n}':>6}`"

    # use ReplyKeyboardRemove() to clear stale keys
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())


def choose_region(update, context):
    """A function for managing the first step of a conversation for regions and provinces data"""

    # Build the keyboard dynamically
    keyboard = get_keyboard('italy')

    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

    # save the user choice for the conversation
    text = update.message.text
    context.user_data['choice'] = text

    if text == '/regione':
        msg = 'Selezionare una regione'
    else: # = '/provincia
        msg = 'Selezionare la regione della provincia desiderata'
 
    update.message.reply_text(msg, reply_markup=reply_markup)
    return REGION

    
def region(update, context):
    """Function for handling data of a region"""
    choice = context.user_data['choice']
    text = update.message.text

    if choice == '/regione':
        # return regional data
        logger.info(f"User {update.message.from_user} requested data of {text}")

        days = 7
        data = R.get_region_cases(text, days)

        if not data:
            # exit and use ReplyKeyboardRemove() to clear stale keys
            update.message.reply_text(f'Nessun dato disponibile per {text}', reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END 

        msg = (
            f"Dati della regione: *{text}*\n\n"
            f"Aggiornamento: *{data[-1]['data']:%a %d %B h.%H:%M}*\n"
        )

        msg += render_data_and_chart(data)

        update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())

        return ConversationHandler.END

    # if we get here, then user is interested in data of a province
    keyboard = get_keyboard(text)

    if not keyboard:
        # user entered wrong text
        update.message.reply_text(f"Nessuna corrispondenza per {text}", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

    update.message.reply_text(
        'Selezionare una provincia',
        reply_markup=reply_markup)

    return PROVINCE


def province(update, context):
    """A function for getting data of a province"""
    text = update.message.text
    logger.info(f"User {update.message.from_user} requested data of {text}")
    
    days = 7
    data = R.get_province_cases(text, days)
    

    if not data:
        # exit and use ReplyKeyboardRemove() to clear stale keys
        update.message.reply_text(f'Nessun dato disponibile per {text}', reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END 

    msg = (
        f"Dati della provincia: *{text}*\n\n"
        f"Aggiornamento: *{data[-1]['data']:%a %d %B h.%H:%M}*\n"
    )

    today_cases= data[-1]['totale_casi']
    yesterday_cases = data[-2]['totale_casi']
    delta = today_cases - yesterday_cases
    msg += f"\n`{'Positivi':>12}: {today_cases:>6n} ({f'{delta:+n}':>6})`"
    
    chart = plot_cases(f'Trend ultimi {len(data)} giorni', data, 'totale_casi')
    msg += f'\n\n\n\n*Casi positivi* (_attualmente e non_)\n`{chart}`'

    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END


def credits(update, context):
    """Return credits"""
    logger.info(f"User {update.message.from_user} requested the credits section")

    msg = (
        "- [Contattami qui](https://twitter.com/i_m_andrea) per info e segnalazioni\n\n"
        "- I [dati usati da questo bot](https://github.com/pcm-dpc/COVID-19) vengono rilasciati dalla Protezione Civile ogni giorno attorno alle ore 18:00\n\n"
        "- Il codice di questo bot è disponibile a [questo link](https://github.com/floatingpurr/covid-19_ita_bot)\n\n"
        "- Bot Icon by Freepik (https://www.flaticon.com/)\n\n"
        "*#restiamoacasa*\n*#tuttoandràbene* 🌈"
    )

    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)


def help(update, context):
    """Help function"""
    logger.info(f"User {update.message.from_user} requested the help")

    msg = (
        "*Comandi disponibili*:\n\n"
        f"{COMMANDS}"
        "*#restiamoacasa*\n*#tuttoandràbene* 🌈"
    )
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)


def cancel(update, context):
    """Stop all"""
    logger.info(f"User {update.message.from_user} canceled the conversation.")
    update.message.reply_text('Operazione annullata',
                              reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def error(update, context):
    """Log Errors caused by Updates."""
    logger.info(f"User {update} caused the error {context.error}")
    msg = (
        "Problema temporaneo sui dati.\nRiprova tra un attimo"
    )
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)

    return ConversationHandler.END 


# This handler must be added last. 
def unknown(update, context):
    """Unknown handler"""
    msg = (
        "Non conosco questo comando\n\n"
        "Questo bot è in continuo aggiornamento, per cui può capitare che i comandi disponibili cambino nel tempo\n\n"
        "I comandi attualmente disponibili sono:\n\n"
        f"{COMMANDS}"
    )

    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)


def main():
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(misc.get_env_variable('API_KEY'), use_context=True)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('italia', nation))
    dp.add_handler(CommandHandler('nuovi', new_cases_per_region))
    dp.add_handler(CommandHandler('help', help))
    dp.add_handler(CommandHandler('credits', credits))

    # Add conversation handler with the states REGION
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('provincia', choose_region),
            CommandHandler('regione', choose_region)
            ],

        states={
            REGION: [MessageHandler(Filters.text, region)],
            PROVINCE : [MessageHandler(Filters.text, province)],

        },

        fallbacks=[CommandHandler('annulla', cancel)]
    )

    dp.add_handler(conv_handler)

    dp.add_error_handler(error)

    dp.add_handler(MessageHandler(Filters.command, unknown))

    # Start the Bot
    updater.start_polling()

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()


if __name__ == '__main__':
    main()
