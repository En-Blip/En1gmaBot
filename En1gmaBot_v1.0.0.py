import socket
import os
import gspread
import time
import sys

'''
INTIAL VERSION
'''

def send_message(irc_socket, channel_name, message):
    irc_socket.send(bytes(f"PRIVMSG #{channel_name} :{message}\r\n", 'UTF-8'))

def reply_to_message(irc_socket, channel_name, response, default_responses, saves_dict, command_desc_dict):
    # get the message and response
    message = response['message'].lower().strip()
    username = response['username'].lower().strip()

    if message.endswith('help'):
        # send the command description
        if ' '.join(message.split()[:-1]) in command_desc_dict.keys():
            send_message(irc_socket, channel_name, f'{command_desc_dict[' '.join(message.split()[:-1])]}')
        else:
            send_message(irc_socket, channel_name, 'unknown command, type $commands for a list of commands')

    elif message in default_responses:
        # send the default response based on the message
        send_message(irc_socket, channel_name, default_responses[message])

    elif message.startswith('$saves'):
        # make sure it's a correct input
        if len(message.split()) != 2:
            send_message(irc_socket, channel_name, 'incorrect command usage, type $saves <username>')
            return

        # increment the savecounter for that user
        user_saves = increment_savecounter(saves_dict, message.split()[1])
        send_message(irc_socket, channel_name, f'{username} has saved the day {user_saves} times.')
    
    elif message.startswith('$command add'):
        # make sure it's a correct input
        if len(message.split()) < 4:
            # send the command description
            send_message(irc_socket, channel_name, 'incorrect command usage, type $command add <command> <response>')
        else:
            # add the command
            command_desc_dict["$" + message.split()[2]] = " ".join(message.split()[3:])
            default_responses["$" + message.split()[2]] = " ".join(message.split()[3:])

            send_message(irc_socket, channel_name, f'command added \'{message.split()[2]}\'')

    else:
        # catch all other messages
        send_message(irc_socket, channel_name, 'unknown command, type $commands for a list of commands')


def increment_savecounter(saves_dict, username):
    '''increment the savecounter for that user
    Parameters: saves_dict (dict), username (str)
    Returns: users number of saves'''

    if username.startswith('@'):
        username = username[1:]

    if username.lower() in saves_dict:
        saves_dict[username] += 1
        return saves_dict[username]
    else:
        saves_dict[username] = 1
        return saves_dict[username]

def clean_response(response):
    '''clean the twitch chat message
    Parameters: response (str) from twitch
    Returns: dict with username and message'''

    # channnel name (whos chat we're in)
    channel_name = response.split('PRIVMSG #')[-1].split(':')[0][:-1]

    # username
    username = response.split('!')[0][1:]

    # pull the message
    message = response.split(f'PRIVMSG #{channel_name} :')[-1]

    return {'message': message, 'username': username, 'channel_name': channel_name}

def authorize_bot(bot_username, channel_name):
    # Set up the connection to the IRC server
    irc_server = 'irc.chat.twitch.tv'
    irc_port = 6667

    # get the oauth token
    # will only need if i start running the bot on a server (see archive)

    oauth_token = os.environ.get('TWITCH_OAUTH_TOKEN')

    # Connect to the IRC server
    irc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    irc_socket.connect((irc_server, irc_port))

    # connect to all channels (if they are live)
    # DO THIS WHEN YOU FIGURE OUT HOW TO DO THIS

    # Send the necessary IRC commands to authorize the bot
    irc_socket.send(bytes(f'PASS {oauth_token}\r\n', 'UTF-8'))
    irc_socket.send(bytes(f'NICK {bot_username}\r\n', 'UTF-8'))
    irc_socket.send(bytes(f'JOIN #{channel_name}\r\n', 'UTF-8'))

    return irc_socket

def run_bot(irc_socket, bot_username, channel_name):
    # pull our spreadsheet values
    command_descriptions, command_outputs, saves_counter = open_sheet()

    default_responses = dict(zip(command_outputs.col_values(1), command_outputs.col_values(2)))
    command_desc_dict = dict(zip(command_descriptions.col_values(1), command_descriptions.col_values(2)))
    saves_ints = [int(i) for i in saves_counter.col_values(2)]
    saves_dict = dict(zip(saves_counter.col_values(1), saves_ints))

    send_message(
        irc_socket, channel_name, 'fingie wingies everyone, En1gmaBot has arrived'
    )

    try:
        # Continuously listen for messages in the chat
        while True:
            response = irc_socket.recv(2048).decode('UTF-8')
            if response.startswith('PING'):
                irc_socket.send(bytes('PONG\r\n', 'UTF-8'))
            else:
                # start by logging the message
                print(response)

                # clean the twitch chat message
                cleaned_response = clean_response(response)
                print(cleaned_response['channel_name'], cleaned_response['username'], cleaned_response['message'])

                # reply to chat messages
                if cleaned_response['message'].startswith('$'):
                    reply_to_message(irc_socket, channel_name, cleaned_response, default_responses, saves_dict, command_desc_dict)
    
    except KeyboardInterrupt:
        # end the code and update everything
        irc_socket.close()

        # update the sheets
        update_sheets(default_responses, saves_dict, command_desc_dict)
        sys.exit(0)
            
def open_sheet():
    '''a function that opens and stores data from my bot google sheet, specifically configured for this sheet
    Parameters: none
    Returns: the sheets (command_sheet, saves_counter)'''
    # open the service account
    gc = gspread.service_account(filename='filepath')

    spreadsheet = gc.open('En1gmaBot Database')
    # open and get the data from the sheets
    command_outputs = spreadsheet.worksheet('Command Outputs') #Commands
    command_descriptions = spreadsheet.worksheet('Command Descriptions') # Command Descriptions
    saves_counter = spreadsheet.worksheet('SavesCounter') #SavesCounter
    return (command_descriptions, command_outputs, saves_counter)

def update_sheets(command_dict, saves_dict, command_desc_dict):
    '''a function that updates the sheets with the most recent data
    Parameters: command_dict, saves_dict, command_desc_dict
    Returns: none'''
    # open the service account
    gc = gspread.service_account(filename='filepath')

    spreadsheet = gc.open('En1gmaBot Database')
    # open and return data to the sheets
    command_outputs = spreadsheet.worksheet('Command Outputs') #Commands
    command_descriptions = spreadsheet.worksheet('Command Descriptions') # Command Descriptions
    saves_counter = spreadsheet.worksheet('SavesCounter') #SavesCounter

    command_outputs.clear()
    command_descriptions.clear()
    saves_counter.clear()

    # update the sheets
    for i in range(len(command_dict.keys()), 0, -1):
        time.sleep(2)
        command_outputs.insert_row([list(command_dict.keys())[i-1], list(command_dict.values())[i-1]], 1)

    for i in range(len(command_desc_dict.keys()), 0, -1):
        time.sleep(2)
        command_descriptions.insert_row([list(command_desc_dict.keys())[i-1], list(command_desc_dict.values())[i-1]], 1)

    for i in range(len(saves_dict.keys()), 0, -1):
        time.sleep(2)
        saves_counter.insert_row([list(saves_dict.keys())[i-1], list(saves_dict.values())[i-1]], 1)

    print('sheets successfully updated')

bot_username = 'en1gmabot'
channel_name = 'en1gmaunknown'

irc_socket = authorize_bot(bot_username, channel_name)
run_bot(irc_socket, bot_username, channel_name)


