import socket
import gspread
import datetime
import sys
import json
import requests
import os
import numpy as np
import warnings
import traceback
warnings.filterwarnings("ignore", category=DeprecationWarning) 

'''
 CHANGELOG
    add autho oauth
    fix live command for oauth

TODO
    fix checksaves command
    close api responses
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
        'eToThe2iPi': '9:00AM',
    },
    'sunday': {
        'pencenter': '2:00PM',
    }
}

SPREADSHEET = "En1gmaBot Database"

class Streamer:
    def __init__(self, settings):
        raid_message = settings['raid_message']
        new_chatter = settings['new_chatter']

class Bot:
    def __init__(self, bot_username, channel_names):
        # initialize bot variables
        self.bot_username = bot_username
        self.channel_names = channel_names
        self.synced_channels = []
        self.mods = {}
        
        # get the oauth token/gspread filename
        # get it from the protected json file
        with open(os.environ.get('JSON_FILEPATH')) as file:
            credentials = json.load(file)

        self.gspread_filename = credentials["GSPREAD_FILENAME"]
        self.oauth_token = credentials["TWITCH_OAUTH_TOKEN"]
        self.client_id = credentials["TWITCH_CLIENT_ID"]
        self.refresh_token = credentials["TWITCH_REFRESH_TOKEN"]
        self.client_secret = credentials["TWITCH_CLIENT_SECRET"]
        
        self.authorize_bot(bot_username) 

        # get spreadsheet values
        self.get_sheet_values()

        # open the service account
        gc = gspread.service_account(filename=self.gspread_filename)
        self.spreadsheet = gc.open(SPREADSHEET)

        # open and return data to the sheets
        self.saves_table = self.spreadsheet.worksheet('SavesCounter') #SavesCounter
        self.quiz_table = self.spreadsheet.worksheet('QuizCounter') #QuizCounter
        self.command_outputs = self.spreadsheet.worksheet('Command Outputs') #Commands
        self.command_desc = self.spreadsheet.worksheet('Command Descriptions') # Command Descriptions

        # populate the question queue with individual queues for streamers
        self.question_queue = {streamer:[] for streamer in self.channel_names}

        # spreadsheet variables
        self.CHANNEL_COLUMNS = ['dondoesmath', 'dannyhighway', 'etothe2ipi', 'pencenter', 'enstucky', 'nsimplexpachinko', 'actualeducation']

        # grab stream-specific variables, like quiz answers and quiz state
        self.quiz_state = [] # stores the channels in "quiz state"
        self.quiz_answers_u = {channel:[] for channel in self.CHANNEL_COLUMNS} # stores the answers for users in thechannels in "quiz state"
        self.quiz_answers_a = {channel:[] for channel in self.CHANNEL_COLUMNS}

    def authorize_bot(self, bot_username):
        # Set up the connection to the IRC server
        irc_server = 'irc.chat.twitch.tv'
        irc_port = 6667

        # Connect to the IRC server
        self.irc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.irc_socket.connect((irc_server, irc_port))

        # Send the necessary IRC commands to authorize the bot
        self.irc_socket.send(bytes(f'PASS oauth:{self.oauth_token}\r\n', 'UTF-8'))
        self.irc_socket.send(bytes(f'NICK {bot_username}\r\n', 'UTF-8'))
        self.irc_socket.send(bytes(f'CAP REQ twitch.tv/tags\r\n', 'UTF-8'))

    def join_chat(self):
        for channel in self.channel_names:
            self.irc_socket.send(bytes(f'JOIN #{channel}\r\n', 'UTF-8'))

    def get_sheet_values(self):
        '''a function that opens and stores data from my bot google sheet, specifically configured for this sheet
        dependencies: open_sheet()'''
        self.command_descriptions, self.default_responses, self.saves_counter, self.quiz_counter, self.user_positions, self.quiz_user_positions = open_sheet(self.gspread_filename)

    def update_sheet_values(self, username, index, first = False):
        '''a function that updates the values in my bot google sheet, specifically configured for this sheet
        dependencies: save_sheet()'''

        # get the index of the user's save in the table
        user_save_index = self.user_positions.index(username)

        # get the dictionary's save values for that user
        user_count = self.saves_counter[username].tolist()

        # update the username (for first time saves)
        self.saves_table.update(range_name=f'A{5+user_save_index}', values=[[username]])

        # update the table with the range of values
        letter = chr(ord('A') + index + 1)

        # update the cell
        if first:
            for i in ["B","C","D","E","F","G","H"]:
                self.saves_table.update(range_name=f'{i}{5+user_save_index}', values=[[user_count[ord(i)-ord('A')-1]]])

                self.saves_table.update(range_name=f'I{5+user_save_index}', values='=sum(INDIRECT("A" & ROW() & ":H" & ROW()))', value_input_option='USER_ENTERED')
        else:
            self.saves_table.update(range_name=f'{letter}{5+user_save_index}', values=[[user_count[index]]])
            #self.saves_table.update(range_name=f'I{5+user_save_index}', values=[[user_count[-1]]])

    def update_quiz_sheet(self, username, index, first = False):
        # get the index of the user's save in the table
        user_quiz_index = self.quiz_user_positions.index(username)

        # get the dictionary's save values for that user
        quiz_user_count = self.quiz_counter[username].tolist()

        # update the username (for first time saves)
        self.quiz_table.update(range_name=f'A{5+user_quiz_index}', values=[[username]])

        # update the table with the range of values
        letter = chr(ord('A') + index + 1)

        # update the cell
        if first:
            for i in ["B","C","D","E","F","G","H"]:
                self.quiz_table.update(range_name=f'{i}{5+user_quiz_index}', values=[[quiz_user_count[ord(i)-ord('A')-1]]])

                self.quiz_table.update(range_name=f'I{5+user_quiz_index}', values='=sum(INDIRECT("A" & ROW() & ":H" & ROW()))', value_input_option='USER_ENTERED')
        else:
            self.quiz_table.update(range_name=f'{letter}{5+user_quiz_index}', values=[[quiz_user_count[index]]])
            #self.quiz_table.update(range_name=f'I{5+user_quiz_index}', values=[[quiz_user_count[-1]]])

        print('sheets successfully updated')
    
    def run(self):

        # store pencenters pop quiz answer
        self.pq_ans = 'πaaskdjhaskhd'

        oauth_reset = False

        while True:
            try:
                # Continuously listen for messages in the chat
                self.run_loop()

                # if the oauth reset is successful then reset our test variable
                if oauth_reset:
                    oauth_reset = False
                    
            except KeyboardInterrupt:
                # refresh oauth so I dont have to manually
                self.refresh_oauth()

                # end the code and update everything
                self.irc_socket.close()

                # update the sheets
                print('ending session')
                sys.exit(0)

            except Exception as e:
                # first try refreshing the oauth token
                if not oauth_reset:
                    # get the traceback
                    tb = sys.exc_info()[2]
                    # find the line number where the exception occurred
                    line_number = traceback.extract_tb(tb)[-1][1]
                    print(f"An exception occurred on line {line_number}: {str(e)}")

                    self.refresh_oauth()

                    # reconnect to the server
                    self.irc_socket.close()

                    # try reconnecting to twitch if twitch disconnected
                    self.authorize_bot(bot_username)

                    self.join_chat()

                    # save a variable to show we already tried resetting the oauth
                    oauth_reset = True
                
    def run_loop(self):
        response = self.irc_socket.recv(2048).decode('UTF-8')
        if response.startswith('PING'):
            self.irc_socket.send(bytes('PONG\r\n', 'UTF-8'))
        else:
            if response.startswith(':'):
                pass
                #return

            cleaned_response = clean_response(response)
            if cleaned_response['mod_status']:
                print(cleaned_response['channel_name'], '(mod)' + cleaned_response['username'] + ':', cleaned_response['message'])
            else:
                print(cleaned_response['channel_name'], cleaned_response['username'] + ':', cleaned_response['message'])

            # sync chat messages between channels
            if len(self.synced_channels) > 1 and cleaned_response['username'] != self.bot_username and cleaned_response['message'].startswith('$send') and cleaned_response['channel_name'] in self.synced_channels:
                # loop through all the channels currently synced
                for channel in self.synced_channels:
                    # if its not the channel the message is in, spread the message
                    if channel != cleaned_response['channel_name']:
                        # create and send the message
                        msg = f'From {cleaned_response["channel_name"]}, {cleaned_response["username"]}: {cleaned_response["message"][6:]}'

                        send_message(self.irc_socket, channel, msg)

            # hack pencenters pop quizzes
            if (cleaned_response['username'] == 'pencenter' or cleaned_response['username'] == 'sh0_bot') and cleaned_response['message'].startswith('What is ') and cleaned_response['message'].split(' ')[3] == '+':
                # get the mesage
                split_message = cleaned_response['message'].split(' ')

                # perform the operation
                self.pq_ans = str(int(split_message[2]) + int(split_message[4]) * int(split_message[6]))

            if cleaned_response['message'].strip() == self.pq_ans:
                # if someone correctly answers the pop quiz, give them a qed
                send_message(self.irc_socket, cleaned_response['channel_name'], f'!qed @{cleaned_response["username"]}')
                self.increment_savecounter(cleaned_response["username"], cleaned_response['channel_name'])
                self.pq_ans = 'πadsaldkjasm'

            if (cleaned_response['username'] == 'pencenter' or cleaned_response['username'] == 'sh0_bot') and ' '.join(cleaned_response['message'].split(' ')[6:]).strip().lower() == 'QED points. pencenQed pencenQed pencenQed'.strip().lower():
                # increment the save counter
                user_saves = self.increment_savecounter(cleaned_response['message'].split(' ')[2], cleaned_response['channel_name'], -1*int(cleaned_response['message'].split(' ')[5]))

            # reply to chat messages
            if cleaned_response['message'].startswith('$') or cleaned_response['message'].startswith('!'):
                self.reply_to_message(cleaned_response)

            # add quiz status to look for quiz answers
            if cleaned_response['channel_name'] in self.quiz_state:
                self.run_quiz(cleaned_response)

    def run_quiz(self, response):
        channel = response['channel_name']
        message = response['message']
        username = response['username']

        # add a function to run the quiz
        if True: #channel == 'actualeducation' or channel == 'en1gmaunknown':
            # collect chat answers
            if (message.startswith('$answer ') or message.startswith('$a ')) and username not in self.quiz_answers_u[channel]:
                self.quiz_answers_u[channel].append(username)
                self.quiz_answers_a[channel].append(' '.join(message.split()[1:]).lower().strip())
            elif username in self.quiz_answers_u[channel] and (message.startswith('$answer ') or message.startswith('$a ')):
                send_message(self.irc_socket, channel, 'you have already answered this question')
    

    def reply_to_message(self, response):
        # get the message and response
        message = response['message'].lower().strip()
        username = response['username'].lower().strip()
        channel_name = response['channel_name'].lower().strip()
        mod_status = response['mod_status']

        if message.endswith('help'):
            # send the command description
            if ' '.join(message.split()[:-1]) in self.command_descriptions.keys():
                send_message(self.irc_socket, channel_name, f'{self.command_descriptions[" ".join(message.split()[:-1])]}')
            else:
                # fix this for command add help
                send_message(self.irc_socket, channel_name, 'unknown command, type $commands for a list of commands')

        elif message in self.default_responses:
            # send the default response based on the message
            send_message(self.irc_socket, channel_name, self.default_responses[message])

        elif message.startswith('$saves ') or (message.startswith('!qed ') and channel_name.lower() == 'pencenter'):
            # make sure theyre a mod
            if not (mod_status or channel_name.lower() == username.lower() or username == 'en1gmaunknown'):
                send_message(self.irc_socket, channel_name, 'you must be a mod to use this command')
                return
                

            # make sure it's a correct input
            if len(message.strip().split()) != 2 and message.split()[-1] and len(message.strip().split()) != 3:
                send_message(self.irc_socket, channel_name, 'incorrect command usage, type $saves <username>')
                return

           # increment the savecounter for that user
            try:
                if len(message.strip().split()) == 3:
                    print(int(message.split()[2]))
                    user_saves = self.increment_savecounter(message.split()[1], channel_name, int(message.split()[-1]))
                else:
                    user_saves = self.increment_savecounter(message.split()[1], channel_name)

            except Exception as e:
                send_message(self.irc_socket, channel_name, e)
                return 
            
            # send an update message if pencenter hasn't already
            if not message.startswith('!qed '):
                send_message(self.irc_socket, channel_name, f'{message.split()[1]} has saved the day {user_saves[self.CHANNEL_COLUMNS.index(channel_name)]} times in {channel_name}.')
            else:
                print(f'{message.split()[1]} has qed\'d {user_saves[self.CHANNEL_COLUMNS.index(channel_name)]} times in {channel_name}.')  

        elif message.startswith('$command add'):
            # make sure it's a correct input
            if len(message.split()) < 4:
                # send the command description
                send_message(self.irc_socket, channel_name, 'incorrect command usage, type $command add <command> <response>')

            elif message.split()[2].startswith('\'') or message.split()[2].startswith('\"'):
                # send an error message
                send_message(self.irc_socket, channel_name, 'incorrect command usage, you do not have to surround your command name in quotes')
            else:
                # add the command to the dictionary
                self.default_responses["$" + message.split()[2]] = " ".join(message.split()[3:])
                
                # insert the rows
                self.command_desc.insert_row(["$" + message.split()[2], " ".join(message.split()[3:])], 2)
                self.command_outputs.insert_row(["$" + message.split()[2], " ".join(message.split()[3:])], 2)

                send_message(self.irc_socket, channel_name, f'command added \'{message.split()[2]}\'')

        elif message == '$syncme':
            # make sure theyre a mod
            if not (mod_status or channel_name.lower() == username.lower() or username.lower() == 'en1gmaunknown'):
                send_message(self.irc_socket, channel_name, 'you must be a mod to use this command')
                return

            # if its a moderator or admin, add them to the sync list
            self.synced_channels.append(channel_name)

            send_message(self.irc_socket, channel_name, 'you are now synced to this channel. use $send <message> to broadcast messages')

        elif message == '$unsyncme':
            # make sure theyre a mod
            if not (mod_status or channel_name.lower() == username.lower() or username.lower() == 'en1gmaunknown'):
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
            selected_username = message.split()[1].lower()

            # nomralize the username
            if selected_username.startswith('@'):
                selected_username = selected_username[1:]

            # pull the saves data
            if selected_username in self.saves_counter:
                user_saves = self.saves_counter[selected_username]
            else:
                user_saves = [0] * (len(self.CHANNEL_COLUMNS) + 1)

            # create a string to show saves
            saves_str = f'{selected_username} has saved the day {user_saves[-1]} times.'

            for i, channel_saves in np.ndenumerate(user_saves):
                if i[0] < 6 and channel_saves > 1:
                    saves_str += f' {channel_saves} times in {self.CHANNEL_COLUMNS[i[0]]},'
                elif i[0] < 6 and channel_saves > 0:
                    saves_str += f' 1 time in {self.CHANNEL_COLUMNS[i[0]]},'

            send_message(self.irc_socket, channel_name, saves_str[:-1] + '.')

        elif message.startswith('$live'):

            failed_last_attempt = False

            while True:

                # use the twitch api to get the live channels that the bot follows
                post_url = 'https://api.twitch.tv/helix/streams/followed?user_id=996414574'
                authorization = f'Bearer {self.oauth_token}'
                client_id = self.client_id

                # send the post request
                response = requests.get(post_url, headers={'Authorization': authorization, 'Client-Id': client_id})

                print(f'request sent: {response}')

                if response.status_code != 200:
                    if not failed_last_attempt:
                        # send error message
                        send_message(self.irc_socket, channel_name, 'failed to get live channels, retrying')
                        failed_last_attempt = True

                        # refresh the oauth token and try again
                        self.refresh_oauth()
                        continue

                    if failed_last_attempt:
                        # send error message
                        send_message(self.irc_socket, channel_name, 'failed to get live channels, please alert En1gma that he sucks')
                        return

                if response.json()['data'] == []:
                    send_message(self.irc_socket, channel_name, 'no live channels')
                    return

                # parse the response for a list of live channels
                data = [i['user_name'] for i in response.json()['data']]

                # create a string with a list of currently live channels
                live_channels = 'Currently Live Channels: ' + ', '.join(data)
                send_message(self.irc_socket, channel_name, live_channels)

                # close our response
                response.close()

                return

        elif message.startswith('$reset'):

            if not (mod_status or channel_name.lower() == username.lower() or username == 'en1gmaunknown'):
                send_message(self.irc_socket, channel_name, 'you must be a mod to use this command')
                return

            self.refresh_oauth()
            self.get_sheet_values()
            send_message(self.irc_socket, channel_name, 'server reloaded')

        elif message.startswith('$leaderboard') or message.startswith('$lb'):

            # check if they are asking for the total leaderboard
            if len(message.split()) == 2:
                # figure out who they are asking for
                if message.split()[1].lower() in self.CHANNEL_COLUMNS:
                    channel_index = self.CHANNEL_COLUMNS.index(channel_name)
                    prefix = f'{channel_name} saves leaderboard: '
                    top_users = np.argsort([x[channel_index] for x in self.saves_counter.values()])
                else:
                    top_users = np.argsort([x[-1] for x in self.saves_counter.values()])
                    prefix = 'Overall saves leaderboard: '
            else:
                channel_index = self.CHANNEL_COLUMNS.index(channel_name)
                prefix = f'{channel_name} saves leaderboard: '
                top_users = np.argsort([x[channel_index] for x in self.saves_counter.values()])
            # create a string with a list of currently live channels
            leaderboard = prefix + ', '.join([list(self.saves_counter.keys())[i] for i in reversed(top_users[-5:])])
            send_message(self.irc_socket, channel_name, leaderboard)

        elif message.startswith('$quizleaderboard') or message.startswith('$quizlb'):

            # check if they are asking for the total leaderboard
            if len(message.split()) == 2:
                # figure out who they are asking for
                if message.split()[1].lower() in self.CHANNEL_COLUMNS:
                    channel_index = self.CHANNEL_COLUMNS.index(channel_name)
                    prefix = f'{channel_name} quiz leaderboard: '
                    top_users = np.argsort([x[channel_index] for x in self.quiz_counter.values()])
                else:
                    top_users = np.argsort([x[-1] for x in self.quiz_counter.values()])
                    prefix = 'Overall quiz leaderboard: '
            else:
                channel_index = self.CHANNEL_COLUMNS.index(channel_name)
                prefix = f'{channel_name} quiz leaderboard: '
                top_users = np.argsort([x[channel_index] for x in self.quiz_counter.values()])
            # create a string with a list of currently live channels
            leaderboard = prefix + ', '.join([list(self.quiz_counter.keys())[i] for i in reversed(top_users[-5:])])
            send_message(self.irc_socket, channel_name, leaderboard)

        elif message.startswith('$queue ') or message.startswith('$q ') or message.startswith('question '):
            self.question_queue[channel_name].append([username, message.split()[1:]])
            send_message(self.irc_socket, channel_name, f"{username} you are in queue position {len(self.question_queue[channel_name])}")
        
        elif message == '$pushqueue' or message == '$pushq':
            # make sure theyre a mod
            if not (mod_status or channel_name.lower() == username.lower()):
                send_message(self.irc_socket, channel_name, 'you must be a mod to use this command')
                return

            # if there are questions in the queue
            if len(self.question_queue[channel_name]) > 0:
                # get the next question
                next_question = self.question_queue[channel_name].pop(0)
                print(channel_name)
                send_message(self.irc_socket, channel_name, f"{next_question[0]} asks {' '.join(next_question[1])}")
            else:
                # if there are no questions in the queue
                print(channel_name)
                send_message(self.irc_socket, channel_name, 'no more questions in queue')

        elif message == '$clearqueue' or message == '$clearq':
            # make sure theyre a mod
            if not (mod_status or channel_name.lower() == username.lower()):
                send_message(self.irc_socket, channel_name, 'you must be a mod to use this command')
                return

            # clear the question queue
            self.question_queue[channel_name] = []
            send_message(self.irc_socket, channel_name, 'question queue cleared')

        # commands specific to quizzes
        elif message == '$startquiz':
            # make sure theyre a mod
            if not (mod_status or channel_name.lower() == username.lower() or username == 'en1gmaunknown'):
                send_message(self.irc_socket, channel_name, 'you must be a mod to use this command')
                return

            if channel_name in self.quiz_state:
                send_message(self.irc_socket, channel_name, 'quiz already started')
                return
            
            self.quiz_state.append(channel_name)
            send_message(self.irc_socket, channel_name, 'quiz started. type $answer/$a <answer> in chat to submit your answer!')
        elif message == '$closequiz' or message == '$stopquiz':
            # make sure theyre a mod
            if not (mod_status or channel_name.lower() == username.lower() or username == 'en1gmaunknown'):
                send_message(self.irc_socket, channel_name, 'you must be a mod to use this command')
                return

            if channel_name not in self.quiz_state:
                send_message(self.irc_socket, channel_name, 'quiz not started')
                return

            self.quiz_state.remove(channel_name)
            send_message(self.irc_socket, channel_name, 'quiz submissions closed')
        elif message.startswith('$scorequiz'):
            # make sure theyre a mod
            if not (mod_status or channel_name.lower() == username.lower() or username == 'en1gmaunknown'):
                send_message(self.irc_socket, channel_name, 'you must be a mod to use this command')
                return
            
            # if they havent closed the quiz yet
            if channel_name in self.quiz_state:
                self.quiz_state.remove(channel_name)
            
            if len(message.split()) != 2:
                send_message(self.irc_socket, channel_name, 'incorrect command usage, type $scorequiz <correct answer>')
                return

            correct_answer = ' '.join(message.split()[1:]).lower().strip()
            total_points = 0

            # variable to see if the first correct answer has been found
            first_correct = False

            for user, answer in zip(self.quiz_answers_u[channel_name], self.quiz_answers_a[channel_name]):
                if answer == correct_answer:
                    if not first_correct:
                        send_message(self.irc_socket, channel_name, f'{user} got the first correct answer!')
                        first_correct = True
                        # increment the quiz savecounter for that user
                        self.increment_quizcounter(user, channel_name, 3)
                        total_points += 3
                    else:
                        self.increment_quizcounter(user, channel_name, 2)
                        total_points += 2
                else:
                    self.increment_quizcounter(user, channel_name, 1)
                    total_points += 1

            # update the spreadsheet with the total points
            letter = chr(ord('A') + self.CHANNEL_COLUMNS.index(channel_name) + 1)
            
            # get the range of values for the column to remove
            valuerange = f'{letter}5:{letter}{len(self.quiz_counter) + 5}'
            values = [[self.quiz_counter[user]] for user in self.quiz_counter.keys()]

            # update the spreadsheet to remove the values
            self.quiz_table.update(valuerange, values)
            
            send_message(self.irc_socket, channel_name, f'Congratulations everyone! {total_points} points were awarded!')

            self.quiz_answers_a[channel_name] = []
            self.quiz_answers_u[channel_name] = []
        elif message == '$quizreset':
            # make sure theyre a mod
            if not (mod_status or channel_name.lower() == username.lower() or username == 'en1gmaunknown'):
                send_message(self.irc_socket, channel_name, 'you must be a mod to use this command')
                return
            
            letter = chr(ord('A') + self.CHANNEL_COLUMNS.index(channel_name) + 1)
            
            # get the range of values for the column to remove
            valuerange = f'{letter}5:{letter}{len(self.quiz_counter) + 5}'
            values = [[0] for _ in range(len(self.quiz_counter))]

            # update the spreadsheet to remove the values
            self.quiz_table.update(valuerange, values)

            self.get_sheet_values()

            send_message(self.irc_socket, channel_name, 'quiz data reset')

        # pass through quiz answers      
        elif message.startswith('$answer ') or message.startswith('$a '):
            if channel_name not in self.quiz_state:
                send_message(self.irc_socket, channel_name, 'quiz is not active')

        elif message.startswith('$') and not message.startswith('$send'):
            # catch all other messages
            send_message(self.irc_socket, channel_name, 'unknown command, type $commands for a list of commands')

    def increment_savecounter(self, username, channel_name, increment=1):
        '''increment the savecounter for that user
        Parameters: username (str), channel_name (str)
        Returns: users number of saves'''

        # remove the @ to normalize usernames
        if username.startswith('@'):
            username = username[1:]

        # strip and lower usernames
        username = username.strip().lower()
        channel_name = channel_name.strip().lower()

        # make sure the channel name is in the list
        if channel_name not in self.CHANNEL_COLUMNS:
            raise Exception(f'{channel_name} not in self.CHANNEL_COLUMNS')

        # make sure the username is in the dict, and add it if its not
        if username in self.saves_counter:
            # increment the total and next save
            self.saves_counter[username][self.CHANNEL_COLUMNS.index(channel_name)] += increment
            self.saves_counter[username][-1] += increment

            # update the sheet
            self.update_sheet_values(username, self.CHANNEL_COLUMNS.index(channel_name))

        else:
            # create the user in the dict and our positions list
            self.saves_counter[username] = np.zeros(len(self.CHANNEL_COLUMNS) + 1, dtype=int)
            self.user_positions.append(username)

            # initialize the total and first save
            self.saves_counter[username][self.CHANNEL_COLUMNS.index(channel_name)] = increment
            #self.saves_counter[username][-1] = increment

            self.update_sheet_values(username, self.CHANNEL_COLUMNS.index(channel_name), first=True)

        return self.saves_counter[username]

# change to quizcounter
    def increment_quizcounter(self, username, channel_name, increment=1):
        '''increment the savecounter for that user
        Parameters: username (str), channel_name (str)
        Returns: users number of saves'''

        # remove the @ to normalize usernames
        if username.startswith('@'):
            username = username[1:]

        # strip and lower usernames
        username = username.strip().lower()
        channel_name = channel_name.strip().lower() #dont think this does anything

        # make sure the channel name is in the list
        if channel_name not in self.CHANNEL_COLUMNS:
            raise Exception(f'{channel_name} not in self.CHANNEL_COLUMNS')

        # make sure the username is in the dict, and add it if its not
        if username in self.quiz_counter:
            # increment the total and next save
            self.quiz_counter[username][self.CHANNEL_COLUMNS.index(channel_name)] += increment
            self.quiz_counter[username][-1] += increment

            # update the spreadsheet for the savecounter
            # dont update the quiz sheet because i am going to do it at the end of scoring
            #self.update_quiz_sheet(username, self.CHANNEL_COLUMNS.index(channel_name))

        else:
            print(username)
            # create the user in the dict and our positions list
            self.quiz_counter[username] = np.zeros(len(self.CHANNEL_COLUMNS) + 1, dtype=int)
            self.quiz_user_positions.append(username)

            # initialize the total and first save
            self.quiz_counter[username][self.CHANNEL_COLUMNS.index(channel_name)] = increment
            #self.quiz_counter[username][-1] = increment

            # dont update the quiz sheet because i am going to do it at the end of scoring
            self.update_quiz_sheet(username, self.CHANNEL_COLUMNS.index(channel_name), first=True)


        return self.quiz_counter[username]


    def refresh_oauth(self):
        # get the parameters for our post request'
        url = "https://id.twitch.tv/oauth2/token"

        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }

        # send the post request
        r = requests.post(url, params=params)

        # update the oauth token
        try:
            self.oauth_token = r.json()['access_token']
            self.refresh_token = r.json()['refresh_token']
            print(f'new oauth token: {self.oauth_token}')
            print(f'new refresh token: {self.refresh_token}')

            # save the oauth token
            with open(os.environ.get('JSON_FILEPATH')) as file:
                credentials = json.load(file)
                credentials["TWITCH_OAUTH_TOKEN"] = self.oauth_token
                credentials["TWITCH_REFRESH_TOKEN"] = self.refresh_token

            with open(os.environ.get('JSON_FILEPATH'), 'w') as file:
                json.dump(credentials, file)

        except:
            print('refresh failed')

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

    # pull the message
    message = response.split(f'PRIVMSG #{channel_name} :')[-1]

    return {'message': message, 'username': username, 'channel_name': channel_name, 'mod_status': mod_status}          

def parse_message_tags(tags):
    '''parse the message tags
    '''

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

    spreadsheet = gc.open(SPREADSHEET)

    # open and get the data from the sheets
    command_outputs = spreadsheet.worksheet('Command Outputs') #Commands
    command_descriptions = spreadsheet.worksheet('Command Descriptions') # Command Descriptions
    saves_counter = spreadsheet.worksheet('SavesCounter') #SavesCounter
    quiz_counter = spreadsheet.worksheet('QuizCounter') #QuizCounter

    # convert the sheets to dictionaries
    default_responses = dict(zip(command_outputs.col_values(1), command_outputs.col_values(2)))
    command_desc_dict = dict(zip(command_descriptions.col_values(1), command_descriptions.col_values(2)))
    saves_ints = np.array([[int(i) for i in saves_counter.col_values(j)[4:]] for j in range(2, 10)])
    quiz_ints = np.array([[int(i) for i in quiz_counter.col_values(j)[4:]] for j in range(2, 10)])
    saves_dict = dict(zip(saves_counter.col_values(1)[4:], saves_ints.transpose()))
    quiz_dict = dict(zip(quiz_counter.col_values(1)[4:], quiz_ints.transpose()))
    quiz_user_positions = quiz_counter.col_values(1)[4:]
    user_positions = saves_counter.col_values(1)[4:]



    return (command_desc_dict, default_responses, saves_dict, quiz_dict, user_positions, quiz_user_positions)




bot_username = 'en1gmabot'
channel_names = ['en1gmabot', 'en1gmaunknown', 'dondoesmath', 'dannyhighway', 'etothe2ipi', 'pencenter', 'enstucky', 'nsimplexpachinko', 'actualeducation']

my_bot = Bot(bot_username, channel_names)
my_bot.join_chat()
my_bot.run()

 