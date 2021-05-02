import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler,ConversationHandler,PollAnswerHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode, ReplyKeyboardRemove
import telegram
import os
import sys
import mysql.connector
import json
from datetime import datetime
from datetime import timedelta
import pytz
import bbdd as db
from math import ceil

# TODO crear funcionalidad para crear un jugador externo. idea tener una sequencia en la base de datos para crear esos id.
# TODO crear funcionalidad parar inscribir y desinscribir otros jugadores ya inscriptos.
# TODO Crear funcionalidad para cargar de que equipo fue cada jugador en un partido.
# TODO crear funcionalidad para que se anote el equipo ganador y la diferencia de goles 
# TODO crear funcionalidad para dar de baja un partido como ya jugado
# TODO crear funcionalidad para que cada uno anote sus goles
# TODO crear funcionalidad para dar estadísticas de partidos ganados y goles
# TODO averiguar como hacer para largar mensajes automáticos y de este modo 2 cosas: que se habilite un partido automáticamente y que a la noche verifique baneados y partidos ya jugados los desactive.
# TODO al final recordar hacer el listado de funciones en fatherbot
# TODO agregar a cada funcion su "info" - Agregar emoticones si se puede!



# configuramos el logger
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# leemos las variables de entorno
TOKEN = os.getenv("TOKEN")
MODE = os.getenv("MODE")

if MODE == 'dev':
    # Acceso local (desarrollo)
    def run(updater):
        # comenzamos a estar atentos al bot, no es lo más eficiente pero lo usamos por el momento
        updater.start_polling()
        updater.idle() # permite finalizar el bot con control + c
        

    # Acceso producción (heroku)
elif MODE == 'prod':
    def run(updater):
        PORT = int(os.environ.get("PORT","8443"))
        HEROKU_APP_NAME = os.environ.get("HEROKU_APP_NAME")
    # add handlers
        updater.start_webhook(listen="0.0.0.0",
                            port=PORT,
                            url_path=TOKEN,
                            webhook_url=f"https://{HEROKU_APP_NAME}.herokuapp.com/{TOKEN}")
        updater.idle()

        
else:
    logger.info('No se especificó el MODE')
    sys.exit()

#------------------------------------------------------------------------------------------------------
# utils:

map_weekday = {
    'l':0, 'lu':0,'lun': 0, 'lunes': 0, 'lune':0,
    'ma':1,'mar': 1, 'martes': 1,'mart':1,'marte':0,
    'mi':2,'mie': 2, 'miercoles': 2, 'mier': 2, 'mierc':2,'mierco':2,'miercol':2,'miercole':2,
    'j':3,'ju':3,'jue': 3, 'jueves': 3,'juev':3,'jueve':3,
    'v':4,'vi':4,'vie': 4, 'viernes': 4, 'vier':4,'viern':4,'vierne':4,
    's':5,'sa':5,  'sab': 5, 'sabado': 5,'saba':5,'sabad':5,
    'd':6,'do':6,'dom': 6, 'domingo': 6,'domi':6,'domin':6,'doming':6,
}

map_weekday_2 = {
    0: 'lunes',
    1: 'martes',
    2: 'miercoles',
    3: 'jueves',
    4: 'viernes',
    5: 'sabado',
    6: 'domingo'
    }

def calculate_date(string_weekday,weeks):
    today = datetime.now(pytz.timezone('America/Argentina/Mendoza')).date()

    if weeks > 0:
        date_new_game = today + timedelta(days=(7 - today.weekday() + 7*(weeks-1)) + map_weekday[string_weekday])
    elif weeks == 0:
        dif_dias = map_weekday[string_weekday] - today.weekday()
        if dif_dias < 0:
            return False
        date_new_game = today + timedelta(days=dif_dias)

    return date_new_game


def headline(headline_bool):
    if headline_bool: 
        return 'T' 
    else: 
        return 'S'

def headline_long(headline_bool):
    if headline_bool: 
        return 'titular' 
    else: 
        return 'suplente'

def par(number):
    return number % 2 == 0

def calculate_need_votes(n_members):
    if par(n_members):
        return int(n_members/2 + 1)
    else:
        return int(ceil(need_votes/2))

# --------------------------------------------------------------------------------------------------------------------------------
# Handlers:


def start(update, context):
    # print(update)

    id_user = update.effective_user['id']
    name = update.effective_user['first_name'] + ' ' + update.effective_user['last_name'] 
    logger.info(f'El usuario "{id_user} - {name}", ha iniciado una conversación')

    update.message.reply_text(f"""
Hola {name} yo soy tu bot:
Los comandos disponibles son: 
    /creategame para crear un nuevo partido.
    /games para ver los partidos disponibles.

Si tienes dudas de como utilizarlos escribe "/comando info" o "/comando i" para más información.
    """)

def creategame(update, context):
    if 'info' in context.args or 'i' in context.args:
        update.message.reply_text("""Para crear un partido debes seguir la siguiente estructura:
        dia\.semanas\.horario\.jugadores\_por\_equipo\. 
        Donde:
        \- *dia*: el día escrito con 3 letras, por ejemplo mie, jue, sab, o el nombre completo del día\.
        \- *semanas*: la cantidad de semanas que deben pasar, 0 hace referencia a la semana actual, 1 a la semana que viene y asi\.
        \- *horario*: un número de 0 a 24\.
        \- *jugadores\_por\_equipo*: puede ser 5,6,7,8,9,11\.""",parse_mode='MarkdownV2')
        return


    ref_date_games = context.args

    if len(ref_date_games) == 0:
        update.message.reply_text("Decime cuando es el partido para poder crearlo!. Escribe '/creategame info' para saber como.")

    for ref_date_game in ref_date_games:
        try:
            # partimos el código recibido
            split_cod = ref_date_game.split('.')
            # verificamos dia de la semana enviado
            if split_cod[0].lower() not in map_weekday:
                update.message.reply_text('No entiendo a que día de la semana te estás refiriendo.')
                return
            # Verificamos las semanas.
            try:
                semanas = int(split_cod[1])
            except:
                update.message.reply_text('La cantidad de semanas debe ser un número entero.')
                return
            # Verificamos el horario
            try:
                horario = int(split_cod[2])
                if horario in (range(0,25)):
                    horario = str(horario).rjust(2,"0")
                else:
                    update.message.reply_text('El horario debe ser un número entre 0 y 24.')
                    return
            except:
                update.message.reply_text('El horario debe ser un número entre 0 y 24.')
                return
            # verificamos el tipo de partido
            try:
                n_jugadores = int(split_cod[3])
                if n_jugadores not in (5,6,7,8,9,11):
                    update.message.reply_text('El número de jugadores por partido puede ser de 5, 6, 7, 8, 9, 11.')   
                    return
            
            except:
                update.message.reply_text('La cantidad de jugadores por partido debe ser un número.')
                return 

            date_new_game = calculate_date(split_cod[0].lower(),semanas)

            if date_new_game == False:
                update.message.reply_text('Estás creando un partido en una fecha que ya paso!. Intenta de nuevo.')
                return

            date = date_new_game.strftime("%Y-%m-%d")
            time = horario + ":00:00"
            weekday = map_weekday_2[date_new_game.weekday()]
            try:
                db.insert_new_game(date, time, n_jugadores)
                update.message.reply_text(f"{update.effective_user.mention_html()} ha creado un partido el día {weekday.capitalize()} de {n_jugadores}vs{n_jugadores} {date_new_game.strftime('%d/%m/%Y')} a las {time[:5]}hs!",parse_mode=ParseMode.HTML)
            except:
                update.message.reply_text('Hubo algún error al crear el partido, intenta de nuevo.')
        except:
            update.message.reply_text("""¡No seas TAN humano y enviame bien el código!
            Recordar el formato: dia.semanas.horario.tipo_de_partido
            Por ejemplo, para un partido de 5v5 del martes de esta semana a las 21 es: /creategame mar.0.21.5""")
            return


def games(update, context):
    if 'info' in context.args or 'i' in context.args:
        update.message.reply_text("""Con este comando verás el listado de los partidos creados y disponibles para anotarse\.
Aparecerá el ID, que es importante cuando hay más de un partido activo ya que tendrás que especificarlo al anotarte\.""",parse_mode='MarkdownV2')
        return

    games_active = db.get_games_active()

    if len(games_active) > 0:
        respuesta = 'Partidos activos: \n'
        for game in games_active:
            date_game = datetime.strptime(str(game[1]), '%Y-%m-%d')
            weekday = map_weekday_2[date_game.weekday()]
            respuesta += f"{game[0]} - {weekday.capitalize()} {date_game.strftime('%d/%m/%Y')} {str(game[2])[:5]}hs de {game[3]}vs{game[3]} \n"
        
        update.message.reply_text(respuesta)
    else:
        update.message.reply_text("No hay partidos activos para anotarse.")

    return



def _insert_player(update, context):
    id_user = update.effective_user['id']
    first_name = update.effective_user['first_name']
    last_name = update.effective_user['last_name'] 
    
    db.insert_new_player(id_user,first_name,last_name)

def annotate(update, context):
    args = context.args

    id_user = update.effective_user['id']
    exist_ban = db.check_exist_ban_player(id_user)
    message_id = update.message['message_id']

    if exist_ban['exist'] == False:
        _insert_player(update, context)
    elif exist_ban['ban'] == True:
        date_ban = exist_ban['date_ban']
        update.message.reply_text(f'Estás ¡¡BAN!! hasta el {date_ban}')
        return

    if len(args) == 1:
        # try:
        id_game = args[0]
        game_info = db.get_game_info(id_game)

        if game_info == None:
            update.message.reply_text(f'El partido con ID {id_game} no existe.')
            return

        if game_info[4] == 0:
            update.message.reply_text(f'El partido con ID {id_game} no está activo.')
            return

        players = db.get_players_game(id_game)
        q_annotated = len(players)
        game_info = db.get_game_info(id_game)
        game_players = int(game_info[3]) * 2
        if q_annotated < game_players:
            headline = True
        else:
            headline = False
        # except:
        #     update.message.reply_text('El ID que se pasó no coincide con el de ningún partido activo.')
        #     return
            
            
    elif len(args) == 0:
        games_active = db.get_games_active()
        # print(games_active)
        if len(games_active) == 1:
            game_info = games_active[0]
            id_game = game_info[0]

            game_players = int(game_info[3]) * 2
            players = db.get_players_game(id_game)
            q_annotated = len(players)

            if q_annotated < game_players:
                headline = True
            else:
                headline = False
        else:
            update.message.reply_text('Hay más de un partido activo para anotarse. Por favor al anotarte pasá el número ID del partido. Para chequear los id: /games')
            # games(update, context)
            return
    
    else:
        update.message.reply_text('Debe pasar el ID del partido a anotarse, en caso de que solo haya 1 activo, no hace falta pasarlo')
        return

    try:
        db.insert_player_in_game(id_user, id_game, headline, message_id)
    except:
        update.message.reply_text('Ya estás anotado en el partido!')
        return

    date_game = datetime.strptime(str(game_info[1]), '%Y-%m-%d')
    weekday = map_weekday_2[date_game.weekday()]
    update.message.reply_text(f"{update.effective_user.mention_html()} se ha anotado al partido del {weekday.capitalize()} {date_game.strftime('%d/%m/%Y')} {str(game_info[2])[:5]}hs como {headline_long(headline)}!",parse_mode=ParseMode.HTML)

def annotated(update, context):
    
    id_games = context.args
    if id_games != []:
        try:
            for id_game in id_games:
                int(id_game)
        except:
            update.message.reply_text("Debes pasar los ID de los partidos. Si no pasas ningun ID los inscriptos a todos los partidos.")
            return
        
        games_active = []
        for id_game in id_games:
            # eliminamos los partidos que no están activos
            game = db.get_game_info(id_game)
            if game == None:
                update.message.reply_text(f"El partido con ID {id_game} no existe.")
                return
            elif game[4] != 1:
                update.message.reply_text(f"El partido con ID {id_game} no está activo.")
                return
            else:
                games_active.append(game)
    # Si no se pasaron parametros, toma todos.        
    else:
        games_active = db.get_games_active()
        
    for game in games_active:
        id_game = game[0]

        players = db.get_players_game(id_game)
        date_game = datetime.strptime(str(game[1]), '%Y-%m-%d')
        weekday = map_weekday_2[date_game.weekday()]
        if len(players) > 0:
            listado = f"{game[0]} - {weekday.capitalize()} {date_game.strftime('%d/%m/%Y')} {str(game[2])[:5]}hs de {game[3]}vs{game[3]}\n"

            for i, player in enumerate(players):
                if player[3] == None:
                    listado += f'{i+1}. {player[1]} {player[2]} - {headline(player[4])} \n'
                else:
                    listado += f'{i+1}. {player[3]} - {headline(player[4])} \n'
        else:
            listado = f"No hay jugadores inscriptos para: {game[0]} - {weekday.capitalize()} {date_game.strftime('%d/%m/%Y')} {str(game[2])[:5]}hs de {game[3]}vs{game[3]}. ID {game[0]}\n"

        update.message.reply_text(listado)

def ban(update, context):
    args = context.args

    if len(args) !=2:
        update.message.reply_text('Deben enviarse dos parametros: \nUno con el ID del jugador a banear (/players para verlo)\nOtro con el codigo "dia.semanas" para especificar hasta cuando, ejemplo si es hasta el miercoles de la próxima semana, es "miercoles.1"')
        return   


    id_player_ban = args[0]
    player_ban_info = db.get_player_info(id_player_ban)
    try:
        split_cod = args[1].split('.')
    except:
        update.message.reply_text('El segundo argumento sirve para especificar hasta cuando durará el ban, tiene el formato "dia.semanas"')
        return   

    try:
        # partimos el código recibido
        # verificamos dia de la semana enviado
        if split_cod[0].lower() not in map_weekday:
            update.message.reply_text('No entiendo a que día de la semana te estás refiriendo.')
            return
        # Verificamos las semanas.
        try:
            semanas = int(split_cod[1])
        except:
            update.message.reply_text('La cantidad de semanas debe ser un número entero.')
            return   
    except:
        update.message.reply_text('Hubo un error en los parametros enviado, por favor chequear el uso de la función con "/ban info"')
        return

    date_ban = calculate_date(split_cod[0].lower(),semanas)
    
    if player_ban_info[3]== None:
        name_player_ban = f'{player_ban_info[1]} {player_ban_info[2]}'
    else:
        name_player_ban = player_ban_info[3]

    poll_ban(update, context, id_player_ban, name_player_ban, date_ban)


def banplayers(update,context):
    players = db.get_ban_players()

    if len(players) == 0:
        update.message.reply_text('No hay pĺayers baneados, que raro que no esté el Mati Care.')
        return
    else:
        listado = 'El listado de baneados: \n'
        for i, player in enumerate(players):
            date_ban = datetime.strptime(str(player[4]), '%Y-%m-%d')
            
            if player[3] == None:
                listado += f'{i+1}. {player[1]} {player[1]} hasta {date_ban.strftime("%d/%m/%Y")} \n'
            else:
                listado += f'{i+1}. {player[3]} hasta {date_ban.strftime("%d/%m/%Y")}\n'

        update.message.reply_text(listado)

def elimban(update,context):
    args = context.args
    
    if len(args) != 1:
        update.message.reply_text('Para eliminar el ban de alguien, debes pasar el ID, con /players lo podés buscar.')
        return
    
    id_player = args[0]

    if int(id_player) == update.effective_user['id']:
        update.message.reply_text('He!! mucha pilleza por acá, no podés eliminar tu propio ban!!')
        return

    player = db.down_ban(id_player)
    update.message.reply_text(f"{update.effective_user.mention_html()} ya no estás baneado!",
        parse_mode=ParseMode.HTML)


def players(update, context):
    players = db.get_players()


    listado = 'Jugadores: \n'
    for i, player in enumerate(players):
        if player[3] == None:
            if player[4] == None:
                listado += f'{i+1}. {player[0]} - {player[1]} {player[2]} \n'
            else:
                date_ban = datetime.strptime(str(player[4]), '%Y-%m-%d')
                listado += f"{i+1}. {player[0]} - {player[1]} {player[2]} - ban {date_ban.strftime('%d/%m/%Y')}  \n"
        else:
            if player[4] == None:
                listado += f'{i+1}. {player[0]} - {player[3]} \n'
            else:
                date_ban = datetime.strptime(str(player[4]), '%Y-%m-%d')
                listado += f"{i+1}. {player[0]} - {player[3]} - ban {date_ban.strftime('%d/%m/%Y')}\n"

    update.message.reply_text(listado)
        

def alias(update, context):
    args = context.args
    alias = ' '.join(args)
    id_user = update.effective_user['id']

    db.set_alias(id_user, alias)

    update.message.reply_text(f'Hola "{alias}"!, ya no te llamaremos por tu viejo  y aburrido nombre :D.')


def poll_ban(update, context, id_player_ban, name_player_ban, date_ban):
    
    """Sends a predefined poll"""
    questions = ["Si!", "Una oportunidad más.."]


    chat_id = update.message.chat['id']
    n_members = my_bot.get_chat_members_count(chat_id)
    need_votes = calculate_need_votes(n_members)
    message = context.bot.send_poll(
        update.effective_chat.id,
        f"VOTACIÓN: ban a {name_player_ban} hasta el {date_ban.strftime('%d/%m/%Y')}:\nSe necesitan {need_votes} votos.",
        questions,
        is_anonymous=False,
        allows_multiple_answers=False,
    )
    # Save some info about the poll the bot_data for later use in receive_poll_answer
    payload = {
        message.poll.id: {
            "type_poll": 'ban',
            "need_votes": need_votes,
            "questions": questions,
            "message_id": message.message_id,
            "chat_id": update.effective_chat.id,
            "id_player_ban": id_player_ban,
            "name_player_ban": name_player_ban,
            "date_ban": date_ban,
            "answers": 0,
            "counter_answers": []
        }
    }
    context.bot_data.update(payload)

def receive_poll_answer(update, context):
    """Summarize a users poll vote"""
    answer = update.poll_answer
    poll_id = answer.poll_id

    chat_id = context.bot_data[poll_id]["chat_id"]
    n_members = my_bot.get_chat_members_count(chat_id)

    try:
        questions = context.bot_data[poll_id]["questions"]
    # this means this poll answer update is from an old poll, we can't do our answering then
    except KeyError:
        return
    selected_options = answer.option_ids
    
    answer_string = ""
    for question_id in selected_options:
        if question_id != selected_options[-1]:
            answer_string += questions[question_id] + " and "
        else:
            answer_string += questions[question_id]
    context.bot.send_message(
        chat_id,
        f"{update.effective_user.mention_html()} dice: {answer_string}!",
        parse_mode=ParseMode.HTML,
    )

    [context.bot_data[poll_id]["counter_answers"].append(option) for option in selected_options]
    
    context.bot_data[poll_id]["answers"] += 1
    # Cerramos la votación cuando la mitad +1 votó
    
    need_votes = context.bot_data[poll_id]["need_votes"]
    # if context.bot_data[poll_id]["answers"] == need_votes:
    if context.bot_data[poll_id]["answers"] == 1:
        context.bot.stop_poll(
            context.bot_data[poll_id]["chat_id"], context.bot_data[poll_id]["message_id"]
        )

        end_votes = context.bot_data[poll_id]["counter_answers"]
        name_player_ban = context.bot_data[poll_id]["name_player_ban"]
        id_player_ban = context.bot_data[poll_id]["id_player_ban"]
        date_ban = context.bot_data[poll_id]["date_ban"]
        
        if end_votes.count(0) > end_votes.count(1):
            respuesta = f'¡¡¡{name_player_ban}  BANEADO LINCE!!! Hasta el {date_ban.strftime("%d/%m/%Y")}'
            player_ban_info = db.ban_player(id_player_ban, date_ban)
        else:
            respuesta = f'{name_player_ban} fiuu safaroli. Portate bien!!'
    
        context.bot.send_message(
            chat_id,
            respuesta,
            # parse_mode=ParseMode.HTML,
        )
    
def deannotate(update, context):
    game = context.args
    id_user = update.effective_user['id']

    if game == []:
        games_active = db.get_games_active()
        if len(games_active) > 1:
            update.message.reply_text(f'Hay más de un partido activo, por favor especifica a qué partido te querés desanotar.')
            return
        else:
            id_game = games_active[0][0]
    else:

        try:
            id_game = game[0]
            try:
                int(id_game)
            except:
                update.message.reply_text(f'El parámetro que le pases debe ser un ID de partido.')
                return
        except:
            update.message.reply_text(f'Debes pasar el ID del partido que quieres desanotarte.')
            return
        if len(game)!= 1:
            update.message.reply_text(f'Debes pasar únicamente el ID del partido que quieres desanotarte.')
            return

    try:
        row_affected = db.deannotate_player(id_user, id_game)
        if row_affected == 1:
            update.message.reply_text(f'Te has desanotado del partido con ID {id_game}.')
            
        elif row_affected == 0:
            update.message.reply_text(f'No estás anotado a ese partido')
            return
    except:
        update.message.reply_text(f'Ha habido un error, verifica si el ID del partido es válido o si estabas anotado en ese partido.')
        return

    recent_sup_player = db.get_recent_sup_player(id_game)
    if recent_sup_player == None:
        return
    else:
        db.set_headline_1(recent_sup_player[0], id_game)
        player_sup  = db.get_player_info(recent_sup_player[0])
        if player_sup[3] == None:
            name = f'{player_sup[1]} {player_sup[2]}'
        else:
            name = player_sup[3]

        update.message.reply_text(f'{name} ha pasado de ser suplente a titular!')



def deactivategame(update, context):
    game = context.args

    try:
        id_game = game[0]
        try:
            int(id_game)
        except:
            update.message.reply_text(f'El parámetro que le pases debe ser un ID de partido.')
    except:
        update.message.reply_text(f'Debes pasar el ID del partido que quieres desactivar.')
        return
    if len(game)!= 1:
        update.message.reply_text(f'Debes pasar únicamente el ID del partido que quieres desactivar.')
        return

    try:
        row_affected = db.deactivate_game(id_game)
        if row_affected == 1:
            update.message.reply_text(f'Se ha desactivado el partido con ID {id_game}.')
            return
        elif row_affected == 0:
            update.message.reply_text(f'No existe un partido con ese ID')
            return
    except:
        update.message.reply_text(f'Ha habido un error, verifica si el ID del partido es válido.')
        return






def botones(update, context):
    button1 = InlineKeyboardButton(
        text='Botoncito',
        callback_data='getDateGame'
    )
    update.message.reply_text(
        text='Haz clic en un botón',
        reply_markup = InlineKeyboardMarkup([
            [button1]
            ])
    )

def getDateGame(update,context):
    print(update.callback_query)


# Un canal de conversación
INPUT_UPPER_TEXT = 0 #
def upper_text(update,context):
    update.message.reply_text('Envia un mensaje nuevo para ponerlo en mayuscula')

    return INPUT_UPPER_TEXT

def input_text(update,context):
    text= update.message.text
    
    update.message.reply_text(text.upper())

    return ConversationHandler.END

# pruebas
def prueba_gets(update,context):
    args = context.args
    chat_id = update.message.chat['id']
    user_id = update.effective_user['id']
    user = my_bot.get_chat_members_count(chat_id)
    print(db.get_recent_sup_player(args[0]))
    # print(update)
    # poll_ban(update, context, 'algo','noimporta')

# obtenemos información de nuestro bot
if __name__ == "__main__":
    my_bot=telegram.Bot(token=TOKEN)
    # print(my_bot.getMe())
    print("BOT CARGADO")

    # enlazamos el updater con el bot
    updater = Updater(my_bot.token, use_context=True)

    # creamos despachador
    dp = updater.dispatcher

    # creamos los manejadores
    dp.add_handler(CommandHandler("start",start))
    dp.add_handler(CommandHandler("creategame",creategame))
    dp.add_handler(CommandHandler("games",games))
    dp.add_handler(CommandHandler("_insert_player", _insert_player))
    dp.add_handler(CommandHandler("annotate", annotate))
    dp.add_handler(CommandHandler("annotated", annotated))
    dp.add_handler(CommandHandler("ban", ban))
    dp.add_handler(CommandHandler("banplayers", banplayers))
    dp.add_handler(CommandHandler("elimban", elimban))
    dp.add_handler(CommandHandler("players", players))
    dp.add_handler(CommandHandler("alias", alias))
    dp.add_handler(CommandHandler("deannotate", deannotate))
    dp.add_handler(CommandHandler("deactivategame", deactivategame))

    dp.add_handler(CommandHandler("prueba_gets",prueba_gets))
    dp.add_handler(CallbackQueryHandler(pattern="getDateGame",callback=getDateGame))
    # dp.add_handler(CommandHandler(Filters.text,echo))
    
    # Poll:
    # dp.add_handler(CommandHandler('poll', poll))
    dp.add_handler(PollAnswerHandler(receive_poll_answer))
    # dp.add_handler(MessageHandler(Filters.poll, receive_poll))

    dp.add_handler(ConversationHandler(
        entry_points=[
            CommandHandler("upper_text",upper_text)],
        states={
            INPUT_UPPER_TEXT:[MessageHandler(Filters.text,input_text)]
        },
        fallbacks=[]
    ))


    run(updater)


