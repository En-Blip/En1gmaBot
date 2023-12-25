import socket
import gspread
import datetime
import time
import sys
import json
import sqlite3
import os
import numpy as np

'''
CHANGELOG
    saves now keeps track of the channels
    auto qed for pencenters channel

TODO
    possible bug when checking saves for a user with no saves
'''

SCHEDULE = {
    'monday': {
        'DannyHighway' : '5:30PM',
        'Enstucky': '4:00PM',
        'Pencenter': '4:00PM'
    },
    'tuesday': {
        'DannyHighway' : '5:30PM',
        'DonDoesMath': '1:00PM',
        'Pencenter': '4:00PM',
    },
    'wednesday': {
        'DannyHighway' : '5:30PM',
        'DonDoesMath (gaming)': '1:00PM',
        'Enstucky': '4:00PM',
    },
    'thursday': {
        'DannyHighway' : '5:30PM',
        'DonDoesMath': '1:00PM',
        'eToThe2iPi': '11:00AM',
    },
    'friday': {
        'DonDoesMath (gaming)': '1:00PM',
        'Enstucky': '4:00PM',
        'eToThe2iPi (gaming)': '6:45PM',
    },
    'saturday': {
        'DonDoesMath': '1:00PM',
        'eToThe2iPi': '8:00AM',
    },
    'sunday': {
        'pencenter': '2:00PM',
    }
}

class Bot:
    def __init__(self, bot_username, channel_names):
        # initialize bot variables
        self.bot_username = bot_username
        self.channel_names = channel_names
        self.synced_channels = []
        self.mods = {}

        self.gspread_filename = 'En1gmaBot_v1.1.1'
        
        # get the oauth token/gspread filename
        # get it from the protected json file
        with open(os.environ.get('JSON_FILEPATH')) as file:
            credentials = json.load(file)

        self.gspread_filename = credentials["GSPREAD_FILENAME"]
        self.oauth_token = f'oauth:{credentials["TWITCH_OAUTH_TOKEN"]}'
        
        self.authorize_bot(bot_username)

        # get spreadsheet values
        self.get_sheet_values()

        # spreadsheet variables
        self.CHANNEL_COLUMNS = ['dondoesmath', 'dannyhighway', 'etothe2ipi', 'pencenter', 'enstucky']

    def authorize_bot(self, bot_username):
        # Set up the connection to the IRC server
        irc_server = 'irc.chat.twitch.tv'
        irc_port = 6667

        # Connect to the IRC server
        self.irc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.irc_socket.connect((irc_server, irc_port))

        # Send the necessary IRC commands to authorize the bot
        self.irc_socket.send(bytes(f'PASS {self.oauth_token}\r\n', 'UTF-8'))
        self.irc_socket.send(bytes(f'NICK {bot_username}\r\n', 'UTF-8'))
        self.irc_socket.send(bytes(f'CAP REQ twitch.tv/tags\r\n', 'UTF-8'))

    def join_chat(self):
        for channel in self.channel_names:
            self.irc_socket.send(bytes(f'JOIN #{channel}\r\n', 'UTF-8'))

    def get_sheet_values(self):
        '''a function that opens and stores data from my bot google sheet, specifically configured for this sheet
        dependencies: open_sheet()'''
        self.command_descriptions, self.default_responses, self.saves_counter = open_sheet(self.gspread_filename)
        
    def update_sheet_values(self):
        '''a function that updates the values in my bot google sheet, specifically configured for this sheet
        dependencies: save_sheet()'''

        # open the service account
        gc = gspread.service_account(filename=self.gspread_filename)

        spreadsheet = gc.open('En1gmaBot Database')
        # open and return data to the sheets
        command_outputs = spreadsheet.worksheet('Command Outputs') #Commands
        command_descriptions = spreadsheet.worksheet('Command Descriptions') # Command Descriptions
        saves_table = spreadsheet.worksheet('SavesCounter') #SavesCounter

        
        command_outputs.clear()
        command_descriptions.clear()

        # update the sheets
        for i in range(len(self.command_descriptions.keys()), 0, -1):
            time.sleep(1)
            command_descriptions.insert_row([list(self.command_descriptions.keys())[i-1], list(self.command_descriptions.values())[i-1]], 1)

        for i in range(len(self.default_responses.keys()), 0, -1):
            time.sleep(1)
            command_outputs.insert_row([list(self.default_responses.keys())[i-1], list(self.default_responses.values())[i-1]], 1)
        

        for i in range(len(self.saves_counter.keys()), 0, -1):
            time.sleep(1)

            # get the save values to update the table range, adding the total on the end
            saves_values = [list(self.saves_counter.keys())[i-1]] + list(self.saves_counter.values())[i-1].tolist()

            # update the table with the range of values
            for j, val in enumerate(saves_values):
                # get the letter of the cell
                letter = chr(ord('A') + j)

                # update the cell
                saves_table.update(f'{letter}{2+i}', val)

        print('sheets successfully updated')
    
    def run(self):

        #for channel_name in self.channel_names:
            #send_message(self.irc_socket, channel_name, 'fingie wingies everyone, En1gmaBot has arrived')

        # store pencenters pop quiz answer
        pq_ans = 'πa'

        try:
            # Continuously listen for messages in the chat
            while True:
                response = self.irc_socket.recv(2048).decode('UTF-8')
                if response.startswith('PING'):
                    self.irc_socket.send(bytes('PONG\r\n', 'UTF-8'))
                else:
                    # clean the twitch chat message and log it
                    if response.startswith(':'):
                        continue

                    cleaned_response = clean_response(response)
                    if cleaned_response['mod_status']:
                        print(cleaned_response['channel_name'], '(mod)' + cleaned_response['username'] + ':', cleaned_response['message'])
                    elif cleaned_response['vip_status']:
                        print(cleaned_response['channel_name'], '(vip)' + cleaned_response['username'] + ':', cleaned_response['message'])
                    else:
                        print(cleaned_response['channel_name'], cleaned_response['username'] + ':', cleaned_response['message'])

                    # sync chat messages between channels
                    if len(self.synced_channels) > 1 and cleaned_response['username'] != self.bot_username and cleaned_response['channel_name'] in self.synced_channels:
                        # loop through all the channels currently synced
                        for channel in self.synced_channels:
                            # if its not the bot, or the channel the message is in, spread the message
                            if channel != cleaned_response['channel_name']:
                                # create and send the message
                                msg = f'From {cleaned_response["channel_name"]}, {cleaned_response["username"]}: {cleaned_response["message"]}'

                                send_message(self.irc_socket, channel, msg)

                    # hack pencenters pop quizzes
                    if cleaned_response['username'] == 'pencenter' and cleaned_response['message'].startswith('What is ') and cleaned_response['message'].split(' ')[3] == '+':
                        # get the mesage
                        split_message = cleaned_response['message'].split(' ')

                        # perform the operation
                        pq_ans = int(split_message[2]) + int(split_message[4]) * int(split_message[6])

                    try:
                        if int(cleaned_response['message'].strip()) == pq_ans:
                            send_message(self.irc_socket, cleaned_response['channel_name'], f'!qed @{cleaned_response["username"]}')
                            pq_ans = 'πa'
                    except:
                        pass

                    # reply to chat messages
                    if cleaned_response['message'].startswith('$') or cleaned_response['message'].startswith('!'):
                        self.reply_to_message(cleaned_response)
        
        except KeyboardInterrupt:
            # end the code and update everything
            self.irc_socket.close()

            # update the sheets
            self.update_sheet_values()
            sys.exit(0)

    def reply_to_message(self, response):
        # get the message and response
        message = response['message'].lower().strip()
        username = response['username'].lower().strip()
        channel_name = response['channel_name'].lower().strip()
        mod_status = response['mod_status']

        if message.endswith('help'):
            # simplify the decription dictionary
            simplified_command_desc_dict = {i[0].split()[0]:i[1] for i in self.command_descriptions.items()}

            # send the command description
            if ' '.join(message.split()[:-1]) in simplified_command_desc_dict.keys():
                send_message(self.irc_socket, channel_name, f'{simplified_command_desc_dict[' '.join(message.split()[:-1])]}')
            else:
                send_message(self.irc_socket, channel_name, 'unknown command, type $commands for a list of commands')

        elif message in self.default_responses:
            # send the default response based on the message
            send_message(self.irc_socket, channel_name, self.default_responses[message])

        elif message.startswith('$saves') or message.startswith('!qed '):
            # make sure theyre a mod
            if not (mod_status or channel_name.lower() == username.lower()):
                send_message(self.irc_socket, channel_name, 'you must be a mod to use this command')
                return

            # make sure it's a correct input
            if len(message.split()) != 2:
                send_message(self.irc_socket, channel_name, 'incorrect command usage, type $saves <username>')
                return

            # increment the savecounter for that user
            try:
                user_saves = self.increment_savecounter(message.split()[1], channel_name)
            except Exception as e:
                send_message(self.irc_socket, channel_name, e)
                return
            
            # send an update message if pencenter hasn't already
            if not message.startswith('!qed '):
                send_message(self.irc_socket, channel_name, f'{message.split()[1]} has saved the day {user_saves[self.CHANNEL_COLUMNS.index(channel_name)]} times in {channel_name}.')
            else:
                print(f'{message.split()[1]} has saved the day {user_saves[self.CHANNEL_COLUMNS.index(channel_name)]} times in {channel_name}.')   

        elif message.startswith('$command add'):
            # make sure it's a correct input
            if len(message.split()) < 4:
                # send the command description
                send_message(self.irc_socket, channel_name, 'incorrect command usage, type $command add <command> <response>')

            elif message.split()[2].startswith('\'') or message.split()[2].startswith('\"'):
                # send an error message
                send_message(self.irc_socket, channel_name, 'incorrect command usage, you do not have to surround your command name in quotes')
            else:
                # add the command
                self.command_descriptions["$" + message.split()[2]] = " ".join(message.split()[3:])
                self.default_responses["$" + message.split()[2]] = " ".join(message.split()[3:])

                send_message(self.irc_socket, channel_name, f'command added \'{message.split()[2]}\'')

        elif message == '$syncme':
            # make sure theyre a mod
            if not (mod_status or channel_name.lower() == username.lower()):
                send_message(self.irc_socket, channel_name, 'you must be a mod to use this command')
                return

            # if its a moderator or admin, add them to the sync list
            self.synced_channels.append(channel_name)

            send_message(self.irc_socket, channel_name, 'you are now synced to this channel')

        elif message == '$unsyncme':
            # make sure theyre a mod
            if not (mod_status or channel_name.lower() == username.lower()):
                send_message(self.irc_socket, channel_name, 'you must be a mod to use this command')
                return

            # if its a moderator or admin, remove them from the sync list
            if channel_name in self.synced_channels:
                self.synced_channels.remove(channel_name)

                send_message(self.irc_socket, channel_name, 'you are no longer synced to this channel')
            else:
                send_message(self.irc_socket, channel_name, 'you are not synced to this channel')
            
        elif message.startswith('$schedule'):
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

            # make sure it's a correct input and see if its default
            if len(message.split()) == 1:

                # get the current date
                current_date = datetime.date.today()
                dotw = days[current_date.weekday()].lower()

                # assemble the message
                message = f'On {dotw} (UTC-8):\n'

                for streamer in SCHEDULE[dotw]:
                    message += f'{streamer} is streaming at {SCHEDULE[dotw][streamer]}\n'

                # send to the chat
                send_message(self.irc_socket, channel_name, message.replace('\n',' '))

            # let the user specify a date
            elif len(message.split()) == 2 and message.split()[1].lower() in SCHEDULE:

                dotw = message.split()[1]

                # assemble the message
                message = f'On {dotw} (UTC-8):\n'

                for streamer in SCHEDULE[dotw]:
                    message += f'{streamer} is streaming at {SCHEDULE[dotw][streamer]}\n'

                # send to the chat
                send_message(self.irc_socket, channel_name, message.replace('\n',' '))
            
            else: 
                send_message(self.irc_socket, channel_name, 'incorrect command usage, type $schedule <day> or $schedule')

        elif message.startswith('$checksaves'):
            # make sure it's a correct input
            if len(message.split()) != 2:
                send_message(self.irc_socket, channel_name, 'incorrect command usage, type $checksaves <username>')
                return

            # check the savecounter for that user
            selected_username = message.split()[1]

            if selected_username.startswith('@'):
                selected_username = selected_username[1:]

            if selected_username.lower() in self.saves_counter:
                user_saves = self.saves_counter[selected_username.lower()]
            else:
                user_saves = [0] * (len(self.CHANNEL_COLUMNS) + 1)

            saves_str = f'{message.split()[1]} has saved the day {sum(user_saves)} times.'

            for i, channel_saves in enumerate(user_saves):
                saves_str += f' {channel_saves} times in {self.CHANNEL_COLUMNS[i]},'

            send_message(self.irc_socket, channel_name, saves_str[:-1] + '.')

        elif message.startswith('$'):
            # catch all other messages
            send_message(self.irc_socket, channel_name, 'unknown command, type $commands for a list of commands')

    def increment_savecounter(self, username, channel_name):
        '''increment the savecounter for that user
        Parameters: username (str), channel_name (str)
        Returns: users number of saves'''

        # remove the @ to normalize usernames
        if username.startswith('@'):
            username = username[1:]

        # make sure the channel name is in the list
        if channel_name not in self.CHANNEL_COLUMNS:
            raise Exception(f'{channel_name} not in self.CHANNEL_COLUMNS')

        # make sure the username is in the dict, and add it if its not
        if username.lower() in self.saves_counter:
            self.saves_counter[username][self.CHANNEL_COLUMNS.index(channel_name)] += 1
            self.saves_counter[username][-1] += 1
            return self.saves_counter[username]
        else:
            # create the user in the dict
            self.saves_counter[username] = [0] * len(self.CHANNEL_COLUMNS)

            # initialize the total and first save
            self.saves_counter[username][self.CHANNEL_COLUMNS.index(channel_name)] = 1
            self.saves_counter[username][-1] = 1
            return self.saves_counter[username]
            

def send_message(irc_socket, channel_name, message):
    irc_socket.send(bytes(f"PRIVMSG #{channel_name} :{message}\r\n", 'UTF-8'))

def clean_response(response):
    '''clean the twitch chat message
    Parameters: response (str) from twitch
    Returns: dict with username and message'''

    tags = parse_message_tags(response.split(' ')[0])

    # channnel name (whos chat we're in)
    channel_name = response.split('PRIVMSG #')[-1].split(' :')[0]

    # username
    username = tags['display-name']

    # user statuses
    mod_status = tags['user-type']
    vip_status = tags['vip']
    subscriber_status = tags['subscriber']

    # pull the message
    message = response.split(f'PRIVMSG #{channel_name} :')[-1]

    return {'message': message, 'username': username, 'channel_name': channel_name, 'mod_status': mod_status, 'vip_status': vip_status, 'subscriber_status': subscriber_status}          

def parse_message_tags(tags):
    '''parse the message tags
    '''

    print(tags)

    # create an empty dictionary
    message_tags = {}

    if tags:
        # split the tags
        tag_list = tags.split(';')

        # put them in the dictionary
        for tag in tag_list:
            key, value = tag.split('=')
            message_tags[key] = value


    return message_tags


def open_sheet(filepath):
    '''a function that opens and stores data from my bot google sheet, specifically configured for this sheet
    Parameters: none
    Returns: the sheets (command_sheet, saves_counter)'''
    # open the service account
    gc = gspread.service_account(filename=filepath)

    spreadsheet = gc.open('En1gmaBot Database')

    # open and get the data from the sheets
    command_outputs = spreadsheet.worksheet('Command Outputs') #Commands
    command_descriptions = spreadsheet.worksheet('Command Descriptions') # Command Descriptions
    saves_counter = spreadsheet.worksheet('SavesCounter') #SavesCounter

    # convert the sheets to dictionaries
    default_responses = dict(zip(command_outputs.col_values(1), command_outputs.col_values(2)))
    command_desc_dict = dict(zip(command_descriptions.col_values(1), command_descriptions.col_values(2)))
    saves_ints = np.array([[int(i) for i in saves_counter.col_values(j)[2:]] for j in range(2, 8)])
    saves_dict = dict(zip(saves_counter.col_values(1)[2:], saves_ints.transpose()))



    return (command_desc_dict, default_responses, saves_dict)




bot_username = 'en1gmabot'
channel_names = ['en1gmabot', 'en1gmaunknown', 'dondoesmath', 'dannyhighway', 'etothe2ipi', 'pencenter', 'enstucky']

my_bot = Bot(bot_username, channel_names)
my_bot.join_chat()
my_bot.run()

 