import socket, string, os, atexit, sys, argparse, urllib2, json
from operator import itemgetter
from datetime import timedelta, datetime
from socket import timeout
from enum import Enum

__DEBUG__ = False

HOST = "irc.twitch.tv"
NAME = ""
PORT = 6667
PASS = ""
CHANNEL = ""
readbuffer = ""
MODT = False
wordsDictionary = {}
filter = []

#Documents time at start of execution
now = datetime.now()

#Setup arguments parser
parser = argparse.ArgumentParser(description='Twitch chat bot.')
parser.add_argument('--channel', type=str, help='Override Settings to switch channel')
parser.add_argument('--words', type=int, help='Number of unique words to listen to until quitting', default=-1)
parser.add_argument('--clear_settings', action='store_true', help='Clears cached settings for name, oAuth, channel, etc.')
parser.add_argument('--simple_chat', action='store_true', help='Outputs only user chat info. (Becomes passive chat window)')
parser.add_argument('--realtime', action='store_true', help='Outputs real time chat data')
parser.add_argument('--top_stream', action='store_true', help='Listens to Twitch channel with highest viewership')
args = parser.parse_args()

#Open "filter" file and load the chat filters
if (os.path.isfile("filter.txt") == True):
    fileIO = open("filter.txt", "r")
    if fileIO.mode == "r":
        filterWords = fileIO.readlines()
        for item in filter:
            filter.append(item.lower())
    fileIO.close()
else:
	print "[Warning] Filter file not found! (filter.txt)"

#Setup application with user settings
data = dict()
dataChanged = False
if os.path.isfile("settings.txt"):
	file = open("settings.txt", "r")
	data = json.load(file)
	file.close()
if args.clear_settings:
    data = dict()
#import name
if data.has_key("NAME"):
	NAME = data["NAME"]
else:
    newValue = raw_input("What is your bot's name?\n")
    NAME = newValue
    data["NAME"] = newValue
    dataChanged = True
#import pass
if data.has_key("PASS"):
	PASS = data["PASS"]
else:
    newValue = raw_input("Obtain an oAuth password at twitchapps.com/tmi\nWhat is your oAuth password??\n")
    data["PASS"] = newValue
    PASS = newValue
    dataChanged = True
#import channel
if data.has_key("CHANNEL"):
	CHANNEL = data["CHANNEL"]
else:
    newValue = raw_input("What channel should I listen to?\n")
    data["CHANNEL"] = newValue
    CHANNEL = newValue
    dataChanged = True

if args.channel:
    CHANNEL = args.channel

if dataChanged:
    file = open("settings.txt", "w+")
    json.dump(data, file)
    file.close()
    print "Settings changed"

@atexit.register
def OutputChatData():
    f = open("output.txt", "w+")
    temp = sorted(wordsDictionary.items(), reverse = True, key=itemgetter(1))
    for k in temp:
        f.write(str(k) + "\n")
    f.close()
    print "Created output file!"

def CheckChannelOnline(channelName):
    url ="https://api.twitch.tv/kraken/streams/" + channelName
    try:
        contents = urllib2.urlopen(url)
    except:
        print "Channel does not exist. Exiting..."
        os._exit(1);
    contents = json.load(contents)
    try:
        if contents.has_key("stream"):
            return "Channel #" + channelName + " is online with " + str(contents["stream"]["viewers"]) + " viewers."
    except:
        print "Stream is offline. Exiting..."
        sys.exit()

def AddLocalEmotesToFilter(channelName):
    global filter
    url ="https://api.twitch.tv/kraken/chat/" + channelName + "/emoticons"
    try:
        contents = urllib2.urlopen(url)
    except:
        print "Channel does not exist - could not load emoticons. Exiting..."
        os._exit(1);
    contents = json.load(contents)
    if contents.has_key("emoticons"):
        #file = open("dilter_debug.txt", "w+")
        for emote in contents["emoticons"]:
            filter.append(emote["regex"].lower())
            #file.write(emote["regex"].lower() + "\n")

def GetTopChannel():
    url ="https://api.twitch.tv/kraken/streams"
    try:
        contents = urllib2.urlopen(url)
    except:
        print "Could not load streams. Exiting..."
        os._exit(1);
    contents = json.load(contents)
    highestStream = contents["streams"][0]
    for stream in contents["streams"]:
        if stream["viewers"] > highestStream["viewers"]:
            highestStream = stream
    chat_prop_url = "https://api.twitch.tv/api/channels/" + highestStream["channel"]["name"] + "/chat_properties"
    try:
        chat_properties = urllib2.urlopen(chat_prop_url)
    except:
        print "Could not load chat properties. Exiting..."
        os._exit(1);
    chat_properties = json.load(chat_properties)
    newHost = chat_properties["chat_servers"][3].split(':')[0]
    global HOST
    HOST = newHost
    print HOST
    return highestStream["channel"]["name"]

if args.top_stream:
    CHANNEL = GetTopChannel()
s = socket.socket()
s.settimeout(.1)
s.connect((HOST,PORT))
s.send("PASS " + PASS + "\r\n")
s.send("NICK " + NAME + "\r\n")
s.send("JOIN #" + CHANNEL + "\r\n")

CheckChannelOnline(CHANNEL)

def ReadChat():
    global readbuffer, MODT
    try:
        readbuffer = readbuffer + s.recv(1024)
    except timeout:
        if False:
            print "[Info] Caught socket recieve timeout"
    temp = string.split(readbuffer, "\n")
    if not MODT:
        print temp
    readbuffer = temp.pop()
    for line in temp:
        if(line[0] == "PING"):
            s.send("PONG %s\r\n" % line[1])

        else:
            parts = string.split(line, ":")

            if "QUIT" not in parts[1] and "JOIN" not in parts[1] and "PART" not in parts[1]:
                try:
                    message = parts[2][:len(parts[2]) -1]
                except:
                    message = ""

                usernamesplit = string.split(parts[1], "!")
                username = usernamesplit[0]

                if MODT:
                    words = message.split(" ")
                    counter = 0
                    strippedMessage = ''
                    for word in words:
                        if word.startswith("!"):
                            #print "Caught Command"
                            break
                        word = word.translate(string.maketrans("",""), string.punctuation).lower()

                        if wordsDictionary.has_key(word):
                            wordsDictionary[word].append(datetime.now())
                            #print "Repeated word: " + word + " x " + str(wordsDictionary[word])
                            strippedMessage = strippedMessage + word + " "
                        else:
                            if word not in filter and not word.startswith("!") and word != '':
                                wordsDictionary[word] = [datetime.now]
                                counter = counter + 1
                                #print "New word: " + word
                                strippedMessage = strippedMessage + word + " "
                    global args
                    if not args.simple_chat and not args.realtime:
                        if strippedMessage != '':
                            print strippedMessage + (" -> (%d new unique words)" % counter)
                    if args.realtime and not args.simple_chat:
                        os.system('cls' if os.name == 'nt' else 'clear')
                        count = 0
                        for k in sorted(wordsDictionary.items(), reverse = True, key=itemgetter(1)):
                            if count < 25:
                                print k
                                count += 1
                    else:
                        print username + ": " + message
                    if len(wordsDictionary) > args.words and args.words != -1:
                        sys.exit()
                else:
                        print "Connecting..."

                for l in parts:
                    if "End of /NAMES list" in l:
                        os.system('cls' if os.name == 'nt' else 'clear')
                        MODT = True
                        global CHANNEL
                        AddLocalEmotesToFilter(CHANNEL)
                        channelStats = CheckChannelOnline(CHANNEL)
                        print "********************************************"
                        print "Connected to Twitch; Listening to chat on channel #" + str(CHANNEL)
                        print channelStats
                        print "********************************************"
@atexit.register
def CloseSocket():
    s.close()


while datetime.now() - now < timedelta(minutes = 10):
    #print str(datetime.now() - now) + " out of " + str(timedelta(minutes = 10))
    ReadChat()
