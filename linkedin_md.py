import os
import csv
from datetime import datetime, timezone
import tzlocal # pip install tzlocal

import sys
sys.path.insert(1, '../hal/')
import person
sys.path.insert(1, '../message_md/')
import message_md
import config
import markdown
import message

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

LinkedIn_Fields = [ 
    LI_CONVERSATION_ID, LI_CONVERSATION_TITLE, LI_FROM, 
    LI_SENDER_PROFILE_URL, LI_TO, LI_RECIPIENT_PROFILE_URLS, 
    LI_DATE_TIME, LI_SUBJECT, LI_CONTENT, LI_FOLDER
]

Profiles_Not_Found = [] # holder for profiles we couldn't find

def parse_header(row, field_map):

    global LinkedIn_Fields

    count = 0
    for col in row:
        for field in LinkedIn_Fields:
            if col == field:
                field_map.append([field, count])
                count += 1

def field_index(field_label, field_map):

    result = -1

    for field in field_map:
        if field[0] == field_label:
            result = field[1]
            break

    return result

def parse_people(row, message, field_map, config):
    """
    Parse the sender and recipient from a row into a Message.

    Parameters:
    row (str): Comma-separated data for the specific message.
    message (Message): The Message object where the data goes.
    field_map (list): The mapping of columns to their field names.
    config (Config): The configuration object containing person data.

    Returns:
    bool: True if both sender and recipient are found, False otherwise.
    """

    found = False
     
    index = field_index(LI_SENDER_PROFILE_URL, field_map)
    from_profile = row[index][len(LI_PROFILE_URL):]

    from_person = config.get_person_by_linkedin_id(from_profile)

    if from_person and len(from_person.slug):
        message.from_slug = from_person.slug

        # this will just get the first person if there are multiple,
        # they are separated by ';'
        index = field_index(LI_RECIPIENT_PROFILE_URLS, field_map)
        to_profile = row[index][len(LI_PROFILE_URL):].split(';')[0]

        to_person = config.get_person_by_linkedin_id(to_profile)

        if to_person and len(to_person.slug):
            message.to_slugs.append(to_person.slug)
            found = True
    else: 
        if from_profile not in Profiles_Not_Found:
            Profiles_Not_Found.append(from_profile)
            print(from_profile + " not found")

    return found

def parse_time(row, message, field_map):
    """
    Parse the date and time from a comma-separated row into a Message.

    Parameters:
    row (str): Comma-separated data for the specific message.
    message (Message): The Message object where the data goes.
    field_map (list): The mapping of columns to their field names.
    
    Notes:
    - Example date/time: `2023-06-11 15:33:58 UTC`
    """
    
    index = field_index(LI_DATE_TIME, field_map)

    # get the time from the message, comes in UTC time ISO format
    date_time = datetime.strptime(row[index][:19], '%Y-%m-%d %H:%M:%S')

    utc_date_time = datetime(date_time.year, date_time.month, date_time.day, 
                           date_time.hour, date_time.minute, date_time.second, 0,
                           tzinfo=timezone.utc)

    # convert to local timezone
    local_timezone = tzlocal.get_localzone()
    localized_date_time = utc_date_time.astimezone(local_timezone)
 
    message.date_str = localized_date_time.strftime("%Y-%m-%d")
    message.time_str = localized_date_time.strftime("%H:%M:%S")
    message.timestamp = localized_date_time.timestamp()
    message.set_date_time()

def parse_row(row, message, field_map, config):
    """
    Parse a single row of LinkedIn messages into a Message object.

    Parameters:
    row (list): The row data from the CSV file.
    message (Message): The Message object to populate.
    field_map (list): The mapping of columns to their field names.
    config (Config): The configuration object containing person data.

    Returns:
    bool: True if the row was successfully parsed, False otherwise.
    """
   
    result = False

    if parse_people(row, message, field_map, config):

        index = field_index(LI_CONTENT, field_map)
        body = row[index]
        
        ignore = ["Message request accepted",
                  "A LinkedIn member left the conversation."]
        
        if body not in ignore:
            message.body = body

            if len(body):
                parse_time(row, message, field_map)
                result = True

    return result

def load_messages(filename, messages, reactions, config):
    """
    Load messages from a LinkedIn CSV file.

    Parameters:
    filename (str): The path to the CSV file.
    messages (list): The list to populate with Message objects.
    reactions (list): Not used for LinkedIn, but required by message_md.
    config (Config): The configuration object containing person data.

    Returns:
    int: The number of messages loaded.
    """

    field_map = []

    with open(filename, 'r') as csv_file:
        reader = csv.reader(csv_file)

        count = 0
        for row in reader:
            if count == 0:
                parse_header(row, field_map)
            else:
                the_message = message.Message()
                if parse_row(row, the_message, field_map, config):
                    messages.append(the_message)
            count += 1
    
    return count

# main

the_messages = []
the_reactions = [] # required by `message_md` but not used for LinkedIn

the_config = config.Config()

if message_md.setup(the_config, markdown.YAML_SERVICE_LINKEDIN):

    # needs to be after setup so the command line parameters override the
    # values defined in the settings file
    message_md.get_markdown(the_config, load_messages, the_messages, the_reactions)