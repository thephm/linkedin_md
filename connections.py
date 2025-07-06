# -----------------------------------------------------------------------------
# 
# Code related to the Signal SQLite `connections` table/CSV export.
#
# The Connections export includes the following fields with the email address
# mostly empty. 
#
#   First Name
#   Last Name
#   URL
#   Email Address
#   Company
#   Position
#   Connected On
#
# -----------------------------------------------------------------------------

import os
import csv
import logging
from datetime import datetime

import sys
sys.path.insert(1, '../message_md/')

sys.path.insert(1, '../hal/')
import person
import identity
#import organization
import position

CONNECTIONS_FILENAME = "connections.csv"

# As at 2025-06-30 there are 7 fields in the `connections.csv` file

CONNECTIONS_FIRST_NAME = "First Name"
CONNECTIONS_LAST_NAME = "Last Name"
CONNECTIONS_URL = "Last Name"
CONNECTIONS_EMAIL_ADDRESS = "Email Address"
CONNECTIONS_COMPANY = "Company"
CONNECTIONS_POSITION = "Position"
CONNECTIONS_CONNECTED_ON = "PositConnected Onion"

ConnectionsFields = [
    CONNECTIONS_FIRST_NAME,
    CONNECTIONS_LAST_NAME, 
    CONNECTIONS_URL,
    CONNECTIONS_EMAIL_ADDRESS,
    CONNECTIONS_COMPANY,
    CONNECTIONS_POSITION,
    CONNECTIONS_CONNECTED_ON
]

def parse_connections_header(row, field_map):
    """
    Parse the header row of the `connections.csv` file and map it to
    the fields defined in `ConnectionsFields`.
    
    Populates the `field_map` with tuples of field names and the corresponding 
    indices in the CSV row.
    
    Parameters:
    - row: The header row from the CSV file.
    - field_map: A list to store the mapping of field names to their indices.

    Returns:
    - None
    """

    global ConnectionsFields

    count = 0
    for col in row:
        for field in ConnectionsFields:
            if col == field:
                field_map.append( [field, count] )
        count += 1

def field_index(field_label, field_map):
    """
    Find the index of a specific field in the `field_map` based on its label.

    Parameters:
    - field_label: Label of the field to find e.g., CONNECTIONS_FIRST_NAME
    - field_map: List mapping field names to their indices in the CSV row.

    Returns:
    - The index of the field if found, otherwise -1.
    """

    result = -1

    for field in field_map:
        if field[0] == field_label:
            result = field[1]
            break

    return result

def store_connections_info(people, the_config, field_map, row):
    """
    Store the connection information from a row in the `connections.csv`
    file into a Person and Organization objects.

    Parameters:
    - peopl: List of Person objects to which the Person will be added to.
    - the_config: Configuration object with source folder and other settings.
    - field_map: List mapping field names to their indices in the CSV row.
    - row: List representing a row from the `message_attachments.csv` file.

    Returns:
    - None
    """
    the_person = person.Person()
    the_identity = identity.Identity()

    the_identity.first_name = row[field_index(CONNECTIONS_FIRST_NAME, field_map)]
    the_identity.last_name = row[field_index(CONNECTIONS_LAST_NAME, field_map)]

    url = row[field_index(CONNECTIONS_URL, field_map)]
    company = row[field_index(CONNECTIONS_COMPANY, field_map)]
    position_name = row[field_index(CONNECTIONS_POSITION, field_map)]

    the_position = position.Position()
    the_position.title = position_name
    the_position.current = True

#    the_position.organization = organization.Organization()
#    company_slug = company.lower().replace(" ", "-").replace(".", "")
#    the_person.organizations.append(company_slug)
    the_person.url = url

    the_person.last_updated = datetime.now().strftime("%Y-%m-%d")
    the_person.connected_on = row[field_index(CONNECTIONS_CONNECTED_ON, field_map)]
    the_person.identity = the_identity
#    the_person.positions.append(the_position)
    
    people.append(the_person)
        
def parse_connections_file(people, the_config):
    """
    Parse the Signal SQLite `message_attachments.csv` file to extract attachment
    metadata and store it in the configuration object.

    Parameters:
    - people: List of Person objects to which people will be added to.
    - the_config: Configuration object containing source folder and other settings.

    Returns:
    - None
    """

    field_map = []

    global ConnectionsFields
  
    try:
        filename = os.path.join(the_config.source_folder, CONNECTIONS_FILENAME)
        
        with open(filename, newline='') as attachments_file:

            connections_reader = csv.reader(attachments_file)
            count = 0
            for row in connections_reader:
                if count == 0:
                    parse_connections_header(row, field_map)
                else:
                    try:
                        store_connections_info(people, the_config, field_map, row)
                    except Exception as e:
                        logging.error(f"store_connections_info failed: {e}")
                count += 1

    except Exception as e:
        logging.error(f"parse_connections_file failed: {e}")
        return
