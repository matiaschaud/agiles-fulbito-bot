import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler,ConversationHandler,PollAnswerHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode, ReplyKeyboardRemove
import os
import sys
import telegram
import mysql.connector
import json
from datetime import datetime
from datetime import timedelta
import pytz





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


# auxiliares:

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

def calculate_date_new_game(string_weekday,weeks):
    today = datetime.now(pytz.timezone('America/Argentina/Mendoza')).date()

    if weeks > 0:
        date_new_game = today + timedelta(days=(7 - today.weekday() + 7*(weeks-1)) + map_weekday[string_weekday])
    elif weeks == 0:
        dif_dias = map_weekday[string_weekday] - today.weekday()
        if dif_dias < 0:
            return False
        date_new_game = today + timedelta(days=dif_dias)

    return date_new_game


def connect(mode):
    if mode == 'dev':
        # Conexión a BBDD
        with open('var_entorno.json','r') as vars_ent:
            vars_ent_json = json.loads(vars_ent.read())

        mydb = mysql.connector.connect(host=vars_ent_json['HOSTNAME_DB'],
                    user=vars_ent_json['USERNAME_DB'],
                    passwd=vars_ent_json['PASSWORD_DB'],
                    db=vars_ent_json['DBNAME_DB'],
                    port=vars_ent_json['PORT_DB'])
        return mydb
    elif mode== 'prod':
        # Conexión a BBDD
        mydb = mysql.connector.connect(host=os.getenv('HOSTNAME_DB'),
                    user=os.getenv('USERNAME_DB'),
                    passwd=os.getenv('PASSWORD_DB'),
                    db=os.getenv('DBNAME_DB'),
                    port=os.getenv('PORT_DB'))
        return mydb
    else:
        raise 'Mode is not defined'

def insert_new_game(date,time,n_jugadores):
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    sql = "INSERT INTO games (date, hour, active, players_per_team) VALUES (%s, %s, %s, %s)"
    val = (date, time,True, n_jugadores)
    mycursor.execute(sql, val)
    mydb.commit()
    mydb.close()

def get_games_active():
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    mycursor.execute("SELECT id, date, hour, players_per_team FROM games WHERE active is true")
    myresult = mycursor.fetchall()
    mydb.close()
    return myresult

def insert_new_player(id_player, first_name, last_name):
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    sql = f"INSERT INTO players (id, first_name, last_name) VALUES (%s, %s, %s)"
    val = (id_player, first_name, last_name)
    try:
        mycursor.execute(sql, val)
        mydb.commit()
    except:
        pass
    mydb.close()

def alter_alias_player(id_player, alias):
    pass

def insert_player_in_game(id_player, id_game, headline):
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    sql = f"INSERT INTO players_games (player_id, game_id, headline) VALUES (%s, %s, %s)"
    val = (id_player, id_game, headline)
    mycursor.execute(sql, val)
    mydb.commit()
    mydb.close()

def check_exist_ban_player(id_player):
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    mycursor.execute(f"SELECT id, until_ban_date FROM players WHERE id = {id_player}")
    myresult = mycursor.fetchone()
    if myresult!= None:
        exist = True
        if myresult[1] == None:
            ban = False
        else:
            date_ban = datetime.strptime(str(myresult[1]), '%Y-%m-%d')
            dif_date = datetime.now(pytz.timezone('America/Argentina/Mendoza')).date() - date_ban
            if dif_date > 0:
                ban = True
                date_ban = date_ban.strftime('%d/%m/%Y')
            else:
                ban = False
                date_ban = None
                down_ban(id_player)
    else:
        exist = False
        ban = None
        date_ban = False
    mydb.close()
    return {'exist': exist, 'ban': ban, 'date_ban': date_ban}

def get_players_game(id_game):
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    mycursor.execute(f"SELECT pg.player_id, p.first_name, p.last_name, p.alias, pg.headline FROM players_games pg LEFT JOIN players p ON p.id = pg.player_id WHERE pg.game_id = {id_game}")
    myresult = mycursor.fetchall()
    mydb.close()
    return myresult

def get_game_info(id_game):
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    mycursor.execute(f"SELECT id, date, hour, players_per_team FROM games WHERE id = {id_game}")
    myresult = mycursor.fetchone()
    mydb.close()
    return myresult

def ban_player(id_player,date):
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    sql = f"UPDATE players SET until_ban_date = %s WHERE id = %s;"
    val = (date ,id_player)
    mycursor.execute(sql, val)
    mydb.commit()
    mydb.close()

def get_ban_players():
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    mycursor.execute("SELECT id, first_name, last_name, alias, until_ban_date FROM players WHERE until_ban_date is not null")
    myresult = mycursor.fetchall()
    mydb.close()
    return myresult

def down_ban(id_player):
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    sql = f"UPDATE players SET until_ban_date = null WHERE id = %s;"
    val = (id_player)
    mycursor.execute(sql, val)
    mydb.commit()
    mycursor.execute(f"SELECT id, first_name, last_name, alias, until_ban_date FROM players WHERE id = {id_player}")
    myresult = mycursor.fetchone()
    mydb.close()
    return myresult

def headline(headline_bool):
    if headline_bool: 
        return 'titular' 
    else: 
        return 'suplente'

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

            date_new_game = calculate_date_new_game(split_cod[0].lower(),semanas)

            if date_new_game == False:
                update.message.reply_text('Estás creando un partido en una fecha que ya paso!. Intenta de nuevo.')
                return

            date = date_new_game.strftime("%Y-%m-%d")
            time = horario + ":00:00"
            weekday = map_weekday_2[date_new_game.weekday()]
            try:
                insert_new_game(date, time, n_jugadores)
                update.message.reply_text(f"{update.effective_user.mention_html()} ha creado un partido el día {weekday.capitalize()} {date_new_game.strftime('%d/%m/%Y')} a las {time[:5]}hs!",parse_mode=ParseMode.HTML)
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

    games_active = get_games_active()

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
    
    insert_new_player(id_user,first_name,last_name)

def annotate(update, context):
    args = context.args

    id_user = update.effective_user['id']
    exist_ban = check_exist_ban_player(id_user)

    if exist_ban['exist'] == False:
        _insert_player(update, context)
    elif exist_ban['ban'] == True:
        date_ban = date_ban['date_ban']
        update.message.reply_text(f'Estás ¡¡BAN!! hasta el {date_ban}')
        return

    if len(args) == 1:
        # try:
        id_game = args[0]
        players = get_players_game(id_game)
        q_annotated = len(players)
        game_info = get_game_info(id_game)
        game_players = int(game_info[3]) * 2
        if q_annotated < game_players:
            headline = True
        else:
            headline = False
        # except:
        #     update.message.reply_text('El ID que se pasó no coincide con el de ningún partido activo.')
        #     return
            
            
    elif len(args) == 0:
        games_active = get_games_active()
        # print(games_active)
        if len(games_active) == 1:
            game_info = games_active[0]
            id_game = game_info[0]
            game_players = int(game_info[3]) * 2
            players = get_players_game(id_game)
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
        update.message.reply_text('No debe pasar ningún argumento en caso de que haya solo 1 partido activo para anotarse o el id del partido al que se quiere anotar.')
        return

    try:
        insert_player_in_game(id_user, id_game, headline)
    except:
        update.message.reply_text('Ya estás anotado en el partido!')
        return

    date_game = datetime.strptime(str(game_info[1]), '%Y-%m-%d')
    weekday = map_weekday_2[date_game.weekday()]
    update.message.reply_text(f"{update.effective_user.mention_html()} se ha anotado al partido del {weekday.capitalize()} {date_game.strftime('%d/%m/%Y')} {str(game_info[2])[:5]}hs!",parse_mode=ParseMode.HTML)

def annotated(update, context):
    # args = context.args
        
    games_active = get_games_active()
    for game in games_active:
        id_game = game[0]
        players = get_players_game(id_game)

        date_game = datetime.strptime(str(game[1]), '%Y-%m-%d')
        weekday = map_weekday_2[date_game.weekday()]
        listado = f"{weekday.capitalize()} {date_game.strftime('%d/%m/%Y')} {str(game[2])[:5]}hs de {game[3]}vs{game[3]} \n"

        for i, player in enumerate(players):
            if player[3] == None:
                listado += f'{i+1}. {player[1]} {player[2]} - {headline(player[4])} \n'
            else:
                listado += f'{i+1}. {player[3]} - {headline(player[4])} \n'

        update.message.reply_text(listado)


def ban(update, context):
    args = context.args

    id_player_ban = args[0]
    split_cod = args[1].split('.')

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


    date_ban = calculate_date_ban(split_cod[0].lower(),semanas)
    date = date_ban.strftime("%Y-%m-%d")

    ban_player(id_player_ban, date)


def banplayer(update,context):
    players = get_ban_players()

    if len(players) == 0:
        update.message.reply_text('No hay pĺayers baneados, que raro que no esté el Mati Care.')
    else:
        listado = 'El listado de baneados: \n'
        for i, player in enumerate(players):
            if player[3] == None:
                listado += f'{i+1}. {player[1]} {player[1]} \n'
            else:
                listado += f'{i+1}. {player[3]} \n'

        update.message.reply_text(listado)

def elimban(update,context):
    args = context.args
    id_player = args[0]

    player = down_ban(id_player)
    update.message.reply_text(f'{player[1]} {player[2]} no está más baneado')









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

# Ejemplo de encuesta!!
def poll(update, context):
    """Sends a predefined poll"""
    questions = ["5 fechas, merecidisimas", "3 fechas, la próxima 5", "1 fecha, solo para que aprenda", "Última oportunidad"]
    message = context.bot.send_poll(
        update.effective_chat.id,
        "Cuantas fechas lo baneamos?",
        questions,
        is_anonymous=False,
        allows_multiple_answers=False,
    )
    # Save some info about the poll the bot_data for later use in receive_poll_answer
    payload = {
        message.poll.id: {
            "questions": questions,
            "message_id": message.message_id,
            "chat_id": update.effective_chat.id,
            "answers": 0,
        }
    }
    context.bot_data.update(payload)


def receive_poll_answer(update, context):
    """Summarize a users poll vote"""
    answer = update.poll_answer
    poll_id = answer.poll_id
    
    print(context.bot_data[poll_id])
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
        context.bot_data[poll_id]["chat_id"],
        f"{update.effective_user.mention_html()} dice: {answer_string}!",
        parse_mode=ParseMode.HTML,
    )
    
    context.bot_data[poll_id]["answers"] += 1
    # Close poll after three participants voted
    if context.bot_data[poll_id]["answers"] == 1:
        context.bot.stop_poll(
            context.bot_data[poll_id]["chat_id"], context.bot_data[poll_id]["message_id"]
        )
    


def receive_poll(update, _):
    """On receiving polls, reply to it by a closed poll copying the received poll"""
    actual_poll = update.effective_message.poll
    # Only need to set the question and options, since all other parameters don't matter for
    # a closed poll
    update.effective_message.reply_poll(
        question=actual_poll.question,
        options=[o.text for o in actual_poll.options],
        # with is_closed true, the poll/quiz is immediately closed
        is_closed=True,
        reply_markup=ReplyKeyboardRemove(),
    )

# pruebas
def prueba_gets(update,context):
    args = context.args
    print(args)
    chat_id = update.message.chat['id']
    user_id = update.effective_user['id']
    user = my_bot.get_chat_members_count(chat_id)
    print(user)

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
    dp.add_handler(CommandHandler("banplayer", banplayer))
    dp.add_handler(CommandHandler("elimban", elimban))


    dp.add_handler(CommandHandler("prueba_gets",prueba_gets))
    dp.add_handler(CallbackQueryHandler(pattern="getDateGame",callback=getDateGame))
    # dp.add_handler(CommandHandler(Filters.text,echo))
    
    # Poll:
    dp.add_handler(CommandHandler('poll', poll))
    dp.add_handler(PollAnswerHandler(receive_poll_answer))
    dp.add_handler(MessageHandler(Filters.poll, receive_poll))

    dp.add_handler(ConversationHandler(
        entry_points=[
            CommandHandler("upper_text",upper_text)],
        states={
            INPUT_UPPER_TEXT:[MessageHandler(Filters.text,input_text)]
        },
        fallbacks=[]
    ))


    run(updater)


