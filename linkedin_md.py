import os
import csv
from datetime import datetime, timezone
import tzlocal # pip install tzlocal

import sys
sys.path.insert(1, '../message_md/')
import message_md
import config
import markdown
import message
import person

#-----------------------------------------------------------------------------
# 
# Parser for LinkedIn `messages.csv` file
#
# @todo - see if there's a way to get attachments, low priority since most of
# my messages in LinkedIn are only text with hyperlinks sometimes
#
#-----------------------------------------------------------------------------
 
# field names

LI_CONVERSATION_ID = "CONVERSATION ID"
LI_CONVERSATION_TITLE = "CONVERSATION TITLE"
LI_FROM = "FROM"
LI_SENDER_PROFILE_URL = "SENDER PROFILE URL"
LI_TO = "TO"
LI_RECIPIENT_PROFILE_URLS = "RECIPIENT PROFILE URLS"
LI_DATE_TIME = "DATE"
LI_SUBJECT = "SUBJECT"
LI_CONTENT = "CONTENT"
LI_FOLDER = "FOLDER"

LI_PROFILE_URL = "https://www.linkedin.com/in/"

LinkedInFields = [ 
    LI_CONVERSATION_ID, LI_CONVERSATION_TITLE, LI_FROM, 
    LI_SENDER_PROFILE_URL, LI_TO, LI_RECIPIENT_PROFILE_URLS, 
    LI_DATE_TIME, LI_SUBJECT, LI_CONTENT, LI_FOLDER
]

def parseHeader(row, fieldMap):

    global LinkedInFields

    count = 0
    for col in row:
        for field in LinkedInFields:
            if col == field:
                fieldMap.append( [field, count] )
                count += 1

def fieldIndex(fieldLabel, fieldMap):

    result = -1

    for field in fieldMap:
        if field[0] == fieldLabel:
            result = field[1]
            break

    return result

# -----------------------------------------------------------------------------
#
# Parse the People from a comma-separated row into a Message
#
# Parameters:
# 
#   - row - comma spearated data for the specific message
#   - message - the Message object where the data goes
#   - fieldMap - the mapping of colums to their field names
#   - config - the Config object
#
# Notes:
#
#   - profile URLS start with LI_PROFILE_URL
#
# Returns
#
#   - True - if a sender and receiver found
#   - False - if either is not found
#
# -----------------------------------------------------------------------------
def parsePeople(row, message, fieldMap, config):

    found = False
     
    index = fieldIndex(LI_SENDER_PROFILE_URL, fieldMap)
    fromProfile = row[index][len(LI_PROFILE_URL):]

    fromPerson = config.getPersonByLinkedInId(fromProfile)

    if fromPerson and len(fromPerson.slug):
        message.sourceSlug = fromPerson.slug

        # this will just get the first person if there are multiple,
        # they are separated by ';'
        index = fieldIndex(LI_RECIPIENT_PROFILE_URLS, fieldMap)
        toProfile = row[index][len(LI_PROFILE_URL):].split(';')[0]

        toPerson = config.getPersonByLinkedInId(toProfile)

        if toPerson and len(toPerson.slug):
            message.destinationSlug = toPerson.slug
            found = True

    return found

# -----------------------------------------------------------------------------
#
# Parse the date and time from a comma-separated row into a Message
#
# Parameters:
# 
#   - row - comma spearated data for the specific message
#   - message - the Message object where the data goes
#   - fieldMap - the mapping of colums to their field names
#
# Notes:
#
#   - example date/time `2023-06-11 15:33:58 UTC`
#
# -----------------------------------------------------------------------------
def parseTime(row, message, fieldMap):
    
    index = fieldIndex(LI_DATE_TIME, fieldMap)

    # get the time from the message, comes in UTC time ISO format
    dateTime = datetime.strptime(row[index][:19], '%Y-%m-%d %H:%M:%S')

    utcDateTime = datetime(dateTime.year, dateTime.month, dateTime.day, 
                           dateTime.hour, dateTime.minute, dateTime.second, 0,
                           tzinfo=timezone.utc)

    # convert to local timezone
    localTimezone = tzlocal.get_localzone()
    localizedDateTime = utcDateTime.astimezone(localTimezone)
 
    message.dateStr = localizedDateTime.strftime("%Y-%m-%d")
    message.timeStr = localizedDateTime.strftime("%H:%M:%S")
    message.timeStamp = localizedDateTime.timestamp()
    message.setDateTime()

# -----------------------------------------------------------------------------
#
# Parse one comma-separated row into a Message object
#
# Parameters:
# 
#   - row - comma spearated data for the specific message
#   - message - the Message object where the data goes
#   - fieldMap - the mapping of colums to their field names
#   - config - the Config object
#
# Notes:
#
#   - profile URLS start with LI_PROFILE_URL
#
# Returns:
#
#   - True - if parsing was successful
#   - False - if not
# 
# -----------------------------------------------------------------------------
def parseRow(row, message, fieldMap, config):
   
    result = False

    if parsePeople(row, message, fieldMap, config):

        index = fieldIndex(LI_CONTENT, fieldMap)
        body = row[index]
        
        ignore = ["Message request accepted",
                  "A LinkedIn member left the conversation."]
        
        if body not in ignore:
            message.body = body

            if len(body):
                parseTime(row, message, fieldMap)
                result = True

    return result

# -----------------------------------------------------------------------------
#
# Load the messages from the CSV file
#
# Parameters:
# 
#   - fileName - the CSV file
#   - message - where the Message objects will go
#   - reactions - not used
#   - config - specific settings 
#
# Notes
#   - the first row is the header row, parse it in case the field order changes
#
# Returns: the number of messages
#
# -----------------------------------------------------------------------------
def loadMessages(fileName, messages, reactions, config):

    fieldMap = []

    with open(fileName, 'r') as csv_file:
        reader = csv.reader(csv_file)

        count = 0
        for row in reader:
            if count == 0:
                parseHeader(row, fieldMap)
            else:
                theMessage = message.Message()
                if parseRow(row, theMessage, fieldMap, config):
                    messages.append(theMessage)
            count += 1
    
    return count

# main

theMessages = []
theReactions = [] # required by `message_md` but not used for LinkedIn

theConfig = config.Config()

if message_md.setup(theConfig, markdown.YAML_SERVICE_LINKEDIN, True):

    # needs to be after setup so the command line parameters override the
    # values defined in the settings file
    message_md.getMarkdown(theConfig, loadMessages, theMessages, theReactions)