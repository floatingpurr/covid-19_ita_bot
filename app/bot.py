#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import locale
import time
from functools import wraps
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, ParseMode, ChatAction
from telegram.ext import Updater, CommandHandler, ConversationHandler, MessageHandler, Filters, PicklePersistence

from utils import misc
from utils.report import Report


if misc.get_env_variable('CONTEXT') == 'Production':
    LEVEL = logging.INFO
else:
    LEVEL = logging.DEBUG

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=LEVEL)

logger = logging.getLogger(__name__)

# set locale
locale.setlocale(locale.LC_ALL, "it_IT.UTF-8")

# Conversation states
IT = 0
REGION, PROVINCE = range(2)
CHECK, BROADCAST = range(2)
FEEDBACK = 0
SEND_REPLY = 0

# Commands rendering
COMMANDS = (
    "/italia - Dati aggregati a livello nazionale\n"
    "/regione - Dati per regione\n"
    "/provincia - Dati per provincia\n"
    "/positivi\_regione - Attualmente positivi per ogni regione\n"
    "/nuovi\_regione - Casi per ogni regione\n"
    "/nuovi\_provincia - Casi per ogni provincia\n"
    "/feedback - invia un feedback o segnala un problema\n"
    "/help - Istruzioni di utilizzo\n"
    "/legenda - Legenda per capire i dati\n"
    "/credits - Informazioni su questo bot\n\n"
)

# the main report object
R = Report()


def send_typing_action(func):
    """Sends typing action while processing func command."""

    @wraps(func)
    def command_func(update, context, *args, **kwargs):
        context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)
        return func(update, context,  *args, **kwargs)

    return command_func


def get_keyboard(keyboard_name):
    """get an generate a keyboard using stored data"""

    # Build the keyboard dynamically
    data_kb = R.get_keyboard(keyboard_name)

    if not data_kb:
        return None

    keyboard = []
    i = 0
    for option in data_kb:
        if option.lower() == 'in fase di definizione/aggiornamento':
            continue
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


def render_data_and_chart(data, ascii=False):
    """
    Return the message `msg` + the chart to render for national and regional data
    Set ascii to True to get an ascii bar chart with the message
    
    """

    msg = ''
    today = data[-1]
    yesterday = data[-2]

    outline = {
        'Positivi' : {
            'today' : int(today['totale_positivi']),
            'diff'  : int(today['variazione_totale_positivi'])
        },
        'Guariti' : {
            'today' : int(today['dimessi_guariti']),
            'diff'  : int(today['dimessi_guariti']) - int(yesterday['dimessi_guariti'])
        },
       'Deceduti' : {
            'today' : int(today['deceduti']),
            'diff'  : int(today['deceduti']) - int(yesterday['deceduti'])
        },
        'Tot. Casi' : {
            'today' : int(today['totale_casi']),
            'diff'  : int(today['nuovi_positivi'])
        },
    }

    for o in outline:
        t = outline[o]['today']
        d = outline[o]['diff']
        if o == 'Tot. Casi':
            msg += f"\n`_____________________________`"
        msg += f"\n`{o:>11}: {t:>7n} ({f'{d:+n}':>6})`"

    msg += '\n\n_(Tra parentesi le variazioni nelle ultime 24h)_'

    if ascii==True:
        chart = plot_cases(f'Ultimi {len(data)} giorni', data, 'totale_positivi')
        msg += f'\n\n\n\n*Trend Attualmente Positivi*\n\n`{chart}`'

    return msg


def render_table(data, label, tot_key, diff_key):
    """ render a dynamic data table """
    table = ''

    for d in data:
        item = d[label][:10] + (d[label][10:] and '.')
        tot = d[tot_key]
        diff = d[diff_key]
        table += f"\n`{item:>11}: {tot:>7n} ({f'{diff:+n}':>6})`"

    return table


@send_typing_action
def start(update, context):
    """Getting started with this bot"""
    logger.info(f"User {update.message.from_user} started the bot")
    
    msg = (
        "*Dati aggiornati dei casi di COVID-19 in Italia*\n\n"
        "_Dati e comandi disponibili_:\n\n"
        f"{COMMANDS}"

   
        "I [dati usati da questo bot](https://github.com/pcm-dpc/COVID-19) sono rilasciati soltanto a fini informativi. Gli aggiornamenti vengono diramati dalla Protezione Civile ogni giorno attorno alle ore 18:00.\n\n*#tuttoandràbene* 🌈"
    )

    # use ReplyKeyboardRemove() to clear stale keys
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN,reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)


@send_typing_action
def nation(update, context):
    """Render national data"""
    logger.info(f"User {update.message.from_user} requested national data")
    days = 15
    data = R.get_national_total_cases(days)

    msg = (
        f"🇮🇹 *Dati nazionali*\n\n"
        f"Aggiornamento: *{data[-1]['data']:%a %d %B h.%H:%M}*\n"
    )

    msg += render_data_and_chart(data = data)

    # get plot
    plot = misc.plotify(title='Trend Attualmente Positivi (Italia)', data = data, key = 'totale_positivi')

    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())
    update.message.reply_photo(caption='Trend Attualmente Positivi (Italia)', photo=plot, reply_markup=ReplyKeyboardRemove())


@send_typing_action
def positive_cases_per_region(update, context):
    """Today's positive cases per region"""
    logger.info(f"User {update.message.from_user} requested positive cases per region")
    data = R.get_regional_positive_cases()

    if not data:
        # exit and use ReplyKeyboardRemove() to clear stale keys
        update.message.reply_text('Nessun dato disponibile', reply_markup=ReplyKeyboardRemove())

    msg = (
        f"*Attualmente positivi per regione*\n\n"
        f"Aggiornamento: *{data[0]['data']:%a %d %B h.%H:%M}*\n" # take the date from the first returned doc
    )

    msg += render_table(
        data=data,
        label='denominazione_regione', 
        tot_key = "totale_positivi",
        diff_key = "variazione_totale_positivi"
        )

    msg += "\n\n_(Tra parentesi l'incremento nelle ultime 24h)_"

    # use ReplyKeyboardRemove() to clear stale keys
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())


@send_typing_action
def new_cases_per_region(update, context):
    """Today's new cases per region"""
    logger.info(f"User {update.message.from_user} requested new cases per region")
    data = R.get_total_cases()

    if not data:
        # exit and use ReplyKeyboardRemove() to clear stale keys
        update.message.reply_text('Nessun dato disponibile', reply_markup=ReplyKeyboardRemove())

    msg = (
        f"*Casi per regione*\n\n"
        f"Aggiornamento: *{data[0]['data']:%a %d %B h.%H:%M}*\n" # take the date from the first returned doc
    )

    msg += render_table(
        data=data,
        label='_id', 
        tot_key = "totale_casi",
        diff_key = "diff"
        )

    msg += '\n\n_(Tra parentesi i nuovi casi nelle ultime 24h)_'

    # use ReplyKeyboardRemove() to clear stale keys
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())


@send_typing_action
def new_cases_per_province(update, context):
    """Today's new cases per province"""

    page_size = 25

    text = update.message.text

    msg = f"*Casi per provincia*\n\n"

    if text != '/next': # page 0
        logger.info(f"User {update.message.from_user} requested new cases per province")

        context.chat_data['offset'] = page_size
        data = R.get_total_cases(region='all', limit = page_size)
        if not data:
            # exit and use ReplyKeyboardRemove() to clear stale keys
            update.message.reply_text('Nessun altro dato disponibile', reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END 

        msg += f"Aggiornamento: *{data[0]['data']:%a %d %B h.%H:%M}*\n\n" # take the date from the first returned doc
        msg += f"_I {page_size} incrementi più rilevanti:_\n"


    else:
        logger.info(f"User {update.message.from_user} requested /next {context.chat_data['offset']}")

        data = R.get_total_cases(region='all', limit = page_size, offset=context.chat_data['offset'] )

        if not data:
            # exit and use ReplyKeyboardRemove() to clear stale keys
            update.message.reply_text('Nessun altro dato disponibile', reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END 

        msg += f"Aggiornamento: *{data[0]['data']:%a %d %B h.%H:%M}*\n\n" # take the date from the first returned doc
        msg += f"_Gli incrementi più rilevanti_\n" 
        msg += f"_(dal {context.chat_data['offset']+1}° al {context.chat_data['offset'] + len(data)}°):_\n"
        # set the new offset
        context.chat_data['offset'] += page_size


    msg += render_table(
        data=data,
        label='_id', 
        tot_key = "totale_casi",
        diff_key = "diff"
        )

    msg += '\n\n_(Tra parentesi i nuovi casi nelle ultime 24h)_\n\n'
    msg += '_Digita_ /next _per la pagina successiva_'

    # use ReplyKeyboardRemove() to clear stale keys
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())

    return IT


@send_typing_action
def choose_region(update, context):
    """A function for managing the first step of a conversation for regions and provinces data"""

    # Build the keyboard dynamically
    keyboard = get_keyboard('italy')

    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

    # save the user choice for the conversation
    text = update.message.text
    context.chat_data['choice'] = text

    if text == '/regione':
        msg = 'Selezionare una regione'
    else: # = '/provincia
        msg = 'Selezionare la regione della provincia desiderata'
 
    update.message.reply_text(msg, reply_markup=reply_markup)
    return REGION


@send_typing_action  
def region(update, context):
    """Function for handling data of a region"""
    choice = context.chat_data['choice']
    text = update.message.text

    if choice == '/regione':
        # return regional data
        logger.info(f"User {update.message.from_user} requested data of {text}")

        days = 15
        data = R.get_region_cases(text, days)
        details = R.get_total_cases(region=text)

        if not data:
            # exit and use ReplyKeyboardRemove() to clear stale keys
            update.message.reply_text(f'Nessun dato disponibile per {text}', reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END 

        msg = (
            f"Dati della regione: *{text}*\n\n"
            f"Aggiornamento: *{data[-1]['data']:%a %d %B h.%H:%M}*\n"
        )

        msg += render_data_and_chart(data)

        msg += '\n\n\n\n*Totale Casi per provincia*\*\n'

        remainder = None # 'in fase di definizione/aggiornamento'
        for d in details:
            if d['_id'].lower() == 'in fase di definizione/aggiornamento':
                remainder = d['totale_casi']
                continue
            elif len(d['_id']) > 11:
                prov = d['_id'][:10] + '.'
            else:
                prov = d['_id']
        
            cases = d['totale_casi']
            diff = d['diff']

            msg += f"\n`{prov:>11}: {cases:>7n} ({f'{diff:+n}':>6})`"

        msg += '\n\n_(Tra parentesi i nuovi casi nelle ultime 24h)_'

        msg +=f'\n\n_*{remainder} casi in fase di aggiornamento_'


        # get plot
        plot = misc.plotify(title=f'Trend Attualmente Positivi ({text})', data = data, key = 'totale_positivi')

        update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())
        update.message.reply_photo(caption=f'Trend Attualmente Positivi ({text})', photo=plot, reply_markup=ReplyKeyboardRemove())

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
        reply_markup=reply_markup
        )

    return PROVINCE


@send_typing_action
def province(update, context):
    """A function for getting data of a province"""
    text = update.message.text
    logger.info(f"User {update.message.from_user} requested data of {text}")
    
    days = 15
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
    msg += f"\n`{'Tot. Casi':>12}: {today_cases:>6n} ({f'{delta:+n}':>6})`"

    msg += '\n\n_(Tra parentesi i nuovi casi nelle ultime 24h)_'
    

    # get plot
    plot = misc.plotify(title=f'Trend Totale Casi ({text})', data = data, key = 'totale_casi')


    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())
    update.message.reply_photo(caption=f'Trend Totale Casi ({text})', photo=plot, reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END


@send_typing_action
def key(update, context):
    """Return the data key"""
    logger.info(f"User {update.message.from_user} requested the legenda")

    msg = (
        "*Legenda*\n\n"
        "- *Totale casi*: i casi totali censiti. Questo valore comprende:\n"
        "\t\t- le persone attualmente positive\n"
        "\t\t- le persone guarite\n"
        "\t\t- i decessi\n\n"
        "- *Positivi*: il numero delle persone attualmente positive\n\n"
    )

    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)


@send_typing_action
def help(update, context):
    """Help function"""
    logger.info(f"User {update.message.from_user} requested the help")

    msg = (
        "*Comandi disponibili*:\n\n"
        f"{COMMANDS}"
        "*#tuttoandràbene* 🌈"
    )
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)


@send_typing_action
def credits(update, context):
    """Return credits"""
    logger.info(f"User {update.message.from_user} requested the credits section")

    msg = (
        "- [Contatti](https://twitter.com/i_m_andrea) per info e segnalazioni su questo bot\n\n"
        "- I [dati usati da questo bot](https://github.com/pcm-dpc/COVID-19) vengono rilasciati dalla Protezione Civile ogni giorno attorno alle ore 18:00\n\n"
        "- Il codice di questo bot è disponibile a [questo link](https://github.com/floatingpurr/covid-19_ita_bot)\n\n"
        "- Bot Icon by Freepik (https://www.flaticon.com/)\n\n"
        "*#tuttoandràbene* 🌈"
    )

    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)


def cancel(update, context):
    """Stop a conversation (generic fallback)"""
    logger.info(f"User {update.message.from_user} cancelled the conversation.")
    return ConversationHandler.END


@send_typing_action
def error(update, context):
    """Log Errors caused by Updates."""
    logger.info(f"User {update} caused the error {context.error}")
    msg = (
        "Problema temporaneo sui dati.\nRiprova tra un attimo"
    )
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)

    return ConversationHandler.END



@send_typing_action
def msg(update, context):
    """Broadcast handler"""
    update.message.reply_text('Tell me...', parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)
    return CHECK


@send_typing_action
def check(update, context):
    """ Check the secret """
    if update.message.text == misc.get_env_variable('DEV_PASS'):
        update.message.reply_text('Insert broadcast message', parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)
        return BROADCAST
    else:
        update.message.reply_text('Bye', parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)
        return ConversationHandler.END


@send_typing_action
def broadcast(update, context):
    """Actual sending function (broadcast)"""

    i = 0
    for i,chat in enumerate(context.dispatcher.chat_data.keys(), start=1):
        if i != 0 and i % 30 == 0:
            time.sleep(1) # avoids the bot ban :)
        logger.info(f"Sending data to {chat}...")
        try:
            context.bot.send_message(chat_id=chat, text=update.message.text)
        except Exception as e:
            print(e)

    msg = f'{i} Messaggi inviati 👍'
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)
    return ConversationHandler.END
    


@send_typing_action
def feedback(update, context):
    """Feedback handler"""
    logger.info(f"User {update.message.from_user} request /feedback")
    update.message.reply_text('Scrivi qui di seguito un feedback su questo bot', parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)
    return FEEDBACK
    

@send_typing_action
def send_feedback(update, context):
    """Send a feedback"""
    logger.info(f"User {update.message.from_user} sent a feedback")
    feedback = f'{update.message.from_user.first_name} with id {update.message.from_user.id} wrote:\n\n{update.message.text}'
    context.bot.send_message(chat_id=misc.get_env_variable('DEV'), text=feedback)
    msg = 'Feedback inviato, grazie!'
    update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)
    return ConversationHandler.END


@send_typing_action
def reply(update, context):
    """Reply handler"""
    splitted_text = update.message.text.split()
    id = splitted_text[1]
    pwd = splitted_text[2]

    if pwd != misc.get_env_variable('DEV_PASS'):
        update.message.reply_text('Bye', parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)
        return ConversationHandler.END

    context.chat_data['reply_to'] = id
    msg = f'Replying to *{id}* ...'
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)
    return SEND_REPLY


@send_typing_action
def send_reply(update, context):
    """Send a reply"""
    id = context.chat_data['reply_to']
    context.bot.send_message(chat_id=id, text='Questo messaggio è visibile solo a te:\n\n' + update.message.text)
    msg = f'Replied to {id}!'
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove(), disable_web_page_preview=True)
    return ConversationHandler.END



# This handler must be added last. 
@send_typing_action
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
    pp = PicklePersistence(filename='_data/conversationbot')

    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(misc.get_env_variable('API_KEY'), persistence=pp, use_context=True)

    dp = updater.dispatcher

    # Basic command handlers
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('italia', nation))
    dp.add_handler(CommandHandler('positivi_regione', positive_cases_per_region))
    dp.add_handler(CommandHandler('nuovi_regione', new_cases_per_region))
    dp.add_handler(CommandHandler('help', help))
    dp.add_handler(CommandHandler('credits', credits))
    dp.add_handler(CommandHandler('legenda', key))


    # Add conversation handler with the states IT 
    new_cases_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('nuovi_provincia', new_cases_per_province)
            ],
        states={
            IT: [CommandHandler('next', new_cases_per_province)],
        },
        fallbacks=[MessageHandler(Filters.command, cancel)],
        allow_reentry=True
    )

    # Command handlers GROUP 1
    dp.add_handler(new_cases_conv_handler, 1)

    # Add conversation handler with the states REGION ans PROVINCE
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('provincia', choose_region),
            CommandHandler('regione', choose_region)
            ],
        states={
            REGION: [MessageHandler(Filters.text & (~ Filters.command), region)],
            PROVINCE : [MessageHandler(Filters.text & (~ Filters.command), province)],
        },
        fallbacks=[MessageHandler(Filters.command, cancel)],
        allow_reentry=True
    )

    # Command handlers GROUP 2
    dp.add_handler(conv_handler, 2)

    # Add conversation handler for broadcasting
    broad_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('msg', msg)
            ],
        states={
            CHECK: [MessageHandler(Filters.text & (~ Filters.command), check)],
            BROADCAST: [MessageHandler(Filters.text & (~ Filters.command), broadcast)],
        },
        fallbacks=[MessageHandler(Filters.command, cancel)],
        allow_reentry=True
    )

    # Command handlers GROUP 3
    dp.add_handler(broad_conv_handler, 3)


    # Add conversation handler for feedbacks
    feedback_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('feedback', feedback)
            ],
        states={
            FEEDBACK: [MessageHandler(Filters.text & (~ Filters.command), send_feedback)],
        },
        fallbacks=[MessageHandler(Filters.command, cancel)],
        allow_reentry=True
    )

    # Command handlers GROUP 4
    dp.add_handler(feedback_conv_handler, 4)


    # Add conversation handler for replies
    reply_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('reply', reply)
            ],
        states={
            SEND_REPLY: [MessageHandler(Filters.text & (~ Filters.command), send_reply)],
        },
        fallbacks=[MessageHandler(Filters.command, cancel)],
        allow_reentry=True
    )

    # Command handlers GROUP 5
    dp.add_handler(reply_conv_handler, 5)

    if misc.get_env_variable('CONTEXT') == 'Production':
        dp.add_error_handler(error)

    dp.add_handler(MessageHandler(Filters.command & (~ Filters.regex('^(\/regione|\/provincia|\/nuovi_provincia|\/next|\/msg|\/feedback|\/reply)$')), unknown))

    # Start the Bot
    updater.start_polling()

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()


if __name__ == '__main__':
    main()
