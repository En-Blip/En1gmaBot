import socket
import os
import gspread
import time
import sys

'''
CHANGELOG:
    converted functions to a broader bot class
    added functionality to join multiple channels at once
    bug fixing
'''

class Bot:
    def __init__(self, bot_username, channel_names):
        # initialize bot variables
        self.bot_username = bot_username
        self.channel_names = channel_names
        
        self.authorize_bot(bot_username)

        # get spreadsheet values
        self.get_sheet_values()

    def authorize_bot(self, bot_username):
        # Set up the connection to the IRC server
        irc_server = 'irc.chat.twitch.tv'
        irc_port = 6667

        # get the oauth token
        # will only need if i start running the bot on a server (see archive)

        oauth_token = 'oauth:k741zqagpr47p7fp86u1l76uvxa7r9'

        # Connect to the IRC server
        self.irc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.irc_socket.connect((irc_server, irc_port))

        # Send the necessary IRC commands to authorize the bot
        self.irc_socket.send(bytes(f'PASS {oauth_token}\r\n', 'UTF-8'))
        self.irc_socket.send(bytes(f'NICK {bot_username}\r\n', 'UTF-8'))

    def join_chat(self):
        for channel in self.channel_names:
            self.irc_socket.send(bytes(f'JOIN #{channel}\r\n', 'UTF-8'))

    def get_sheet_values(self):
        '''a function that opens and stores data from my bot google sheet, specifically configured for this sheet
        dependencies: open_sheet()'''
        self.command_descriptions, self.default_responses, self.saves_counter = open_sheet()
        
    def update_sheet_values(self):
        '''a function that updates the values in my bot google sheet, specifically configured for this sheet
        dependencies: save_sheet()'''
        # open the service account
        gc = gspread.service_account(filename='/Users/noahvickerson/Desktop/VSCode/twitchBot/botenv/en1gmabot-database.json')

        spreadsheet = gc.open('En1gmaBot Database')
        # open and return data to the sheets
        command_outputs = spreadsheet.worksheet('Command Outputs') #Commands
        command_descriptions = spreadsheet.worksheet('Command Descriptions') # Command Descriptions
        saves_counter = spreadsheet.worksheet('SavesCounter') #SavesCounter

        command_outputs.clear()
        command_descriptions.clear()
        saves_counter.clear()

        # update the sheets
        for i in range(len(self.command_descriptions.keys()), 0, -1):
            time.sleep(1)
            command_descriptions.insert_row([list(self.command_descriptions.keys())[i-1], list(self.command_descriptions.values())[i-1]], 1)

        for i in range(len(self.default_responses.keys()), 0, -1):
            time.sleep(1)
            command_outputs.insert_row([list(self.default_responses.keys())[i-1], list(self.default_responses.values())[i-1]], 1)
        
        for i in range(len(self.saves_counter.keys()), 0, -1):
            time.sleep(1)
            saves_counter.insert_row([list(self.saves_counter.keys())[i-1], list(self.saves_counter.values())[i-1]], 1)

        print('sheets successfully updated')
    
    def run(self):

        for channel_name in self.channel_names:
            send_message(
                self.irc_socket, channel_name, 'En1gmaBot has arrived. Type $commands to see the list of commands'
            )

        try:
            # Continuously listen for messages in the chat
            while True:
                response = self.irc_socket.recv(2048).decode('UTF-8')
                if response.startswith('PING'):
                    self.irc_socket.send(bytes('PONG\r\n', 'UTF-8'))
                else:
                    # start by logging the message
                    print(response)

                    # clean the twitch chat message
                    cleaned_response = clean_response(response)
                    print(cleaned_response['channel_name'], cleaned_response['username'], cleaned_response['message'])

                    # reply to chat messages
                    if cleaned_response['message'].startswith('$'):
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

        elif message.startswith('$saves'):
            # make sure it's a correct input
            if len(message.split()) != 2:
                send_message(self.irc_socket, channel_name, 'incorrect command usage, type $saves <username>')
                return

            # increment the savecounter for that user

            user_saves = self.increment_savecounter(message.split()[1])
            send_message(self.irc_socket, channel_name, f'{message.split()[1]} has saved the day {user_saves} times.')
        
        elif message.startswith('$command add'):
            # make sure it's a correct input
            if len(message.split()) < 4:
                # send the command description
                send_message(self.irc_socket, channel_name, 'incorrect command usage, type $command add <command> <response>')
            else:
                # add the command
                self.command_descriptions["$" + message.split()[2]] = " ".join(message.split()[3:])
                self.default_responses["$" + message.split()[2]] = " ".join(message.split()[3:])

                send_message(self.irc_socket, channel_name, f'command added \'{message.split()[2]}\'')

        else:
            # catch all other messages
            send_message(self.irc_socket, channel_name, 'unknown command, type $commands for a list of commands')

    def increment_savecounter(self, username):
        '''increment the savecounter for that user
        Parameters: saves_dict (dict), username (str)
        Returns: users number of saves'''

        if username.startswith('@'):
            username = username[1:]

        if username.lower() in self.saves_counter:
            self.saves_counter[username] += 1
            return self.saves_counter[username]
        else:
            self.saves_counter[username] = 1
            return self.saves_counter[username]


def send_message(irc_socket, channel_name, message):
    irc_socket.send(bytes(f"PRIVMSG #{channel_name} :{message}\r\n", 'UTF-8'))

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

def open_sheet():
    '''a function that opens and stores data from my bot google sheet, specifically configured for this sheet
    Parameters: none
    Returns: the sheets (command_sheet, saves_counter)'''
    # open the service account
    gc = gspread.service_account(filename='/Users/noahvickerson/Desktop/VSCode/twitchBot/botenv/en1gmabot-database.json')

    spreadsheet = gc.open('En1gmaBot Database')

    # open and get the data from the sheets
    command_outputs = spreadsheet.worksheet('Command Outputs') #Commands
    command_descriptions = spreadsheet.worksheet('Command Descriptions') # Command Descriptions
    saves_counter = spreadsheet.worksheet('SavesCounter') #SavesCounter

    # convert the sheets to dictionaries
    default_responses = dict(zip(command_outputs.col_values(1), command_outputs.col_values(2)))
    command_desc_dict = dict(zip(command_descriptions.col_values(1), command_descriptions.col_values(2)))
    saves_ints = [int(i) for i in saves_counter.col_values(2)]
    saves_dict = dict(zip(saves_counter.col_values(1), saves_ints))


    return (command_desc_dict, default_responses, saves_dict)


bot_username = 'en1gmabot'
channel_names = ['etothe2ipi', 'dannyhighway']

my_bot = Bot(bot_username, channel_names)
my_bot.join_chat()
my_bot.run()
