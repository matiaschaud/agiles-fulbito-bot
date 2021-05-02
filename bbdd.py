
import os
# import sys
import mysql.connector
import json
from datetime import datetime
# from datetime import timedelta
import pytz

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
    mycursor.execute("SELECT id, date, hour, players_per_team, active FROM games WHERE active is true")
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

def set_alias(id_player, alias):
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    sql = f"UPDATE players SET alias = %s WHERE id = %s;"
    val = (alias,id_player)
    mycursor.execute(sql, val)
    mydb.commit()
    mydb.close()

def insert_player_in_game(id_player, id_game, headline, message_id):
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    sql = f"INSERT INTO players_games (player_id, game_id, headline, message_id) VALUES (%s, %s, %s, %s)"
    val = (id_player, id_game, headline, message_id)
    mycursor.execute(sql, val)
    mydb.commit()
    mydb.close()

def check_exist_ban_player(id_player):
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    mycursor.execute(f"SELECT id, until_ban_date FROM players WHERE id = {id_player}")
    myresult = mycursor.fetchone()


    if myresult != None:
        exist = True
        if myresult[1] == None:
            ban = False
            date_ban = None
        else:
            date_ban = datetime.strptime(str(myresult[1]), '%Y-%m-%d')
            dif_date = (date_ban.date() - datetime.now(pytz.timezone('America/Argentina/Mendoza')).date()).days
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
    mycursor.execute(f"SELECT id, date, hour, players_per_team, active FROM games WHERE id = {id_game}")
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
    mycursor.execute(f"SELECT id, first_name, last_name, alias, until_ban_date FROM players WHERE id = {id_player}")
    myresult = mycursor.fetchone()
    mydb.close()
    return myresult

def get_ban_players():
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    mycursor.execute("SELECT id, first_name, last_name, alias, until_ban_date FROM players WHERE until_ban_date is not null")
    myresult = mycursor.fetchall()
    mydb.close()
    return myresult

def get_players():
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    mycursor.execute("SELECT id, first_name, last_name, alias, until_ban_date FROM players")
    myresult = mycursor.fetchall()
    mydb.close()
    return myresult

def get_player_info(id_player):
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    mycursor.execute(f"SELECT id, first_name, last_name, alias, until_ban_date FROM players WHERE id = {id_player}")
    myresult = mycursor.fetchone()
    mydb.close()
    return myresult

def down_ban(id_player):
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    mycursor.execute(f"UPDATE players SET until_ban_date = null WHERE id = {id_player}")
    mydb.commit()
    mycursor.execute(f"SELECT id, first_name, last_name, alias, until_ban_date FROM players WHERE id = {id_player}")
    myresult = mycursor.fetchone()
    mydb.close()
    return myresult

def deannotate_player(id_player, id_game):
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    mycursor.execute(f"DELETE FROM players_games WHERE player_id = {id_player} and game_id = {id_game}")
    row_count = mycursor.rowcount
    mydb.commit()
    return row_count

def deactivate_game(id_game):
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    mycursor.execute(f"UPDATE games SET active = false WHERE id = {id_game}")
    row_count = mycursor.rowcount
    mydb.commit()
    return row_count

def get_recent_sup_player(id_game):
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    mycursor.execute(f"SELECT player_id FROM players_games WHERE game_id = {id_game} AND headline = false ORDER BY message_id asc")
    myresult = mycursor.fetchone()
    mydb.close()
    return myresult

def set_headline_1(id_player, id_game):
    mydb = connect(os.getenv("MODE"))
    mycursor = mydb.cursor()
    mycursor.execute(f"UPDATE players_games SET headline = true WHERE game_id = {id_game} and player_id = {id_player}")
    # row_count = mycursor.rowcount
    mydb.commit()
    # return row_count