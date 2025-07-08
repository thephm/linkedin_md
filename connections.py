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
import re

import sys
sys.path.insert(1, '../message_md/')

sys.path.insert(1, '../hal/')
import person
import identity
import organization
import position

CONNECTIONS_FILENAME = "connections.csv"

# As at 2025-06-30 there are 7 fields in the `connections.csv` file

CONNECTIONS_FIRST_NAME = "First Name"
CONNECTIONS_LAST_NAME = "Last Name"
CONNECTIONS_URL = "URL"
CONNECTIONS_EMAIL_ADDRESS = "Email Address"
CONNECTIONS_COMPANY = "Company"
CONNECTIONS_POSITION = "Position"
CONNECTIONS_CONNECTED_ON = "Connected On"

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

def clean_company_name(name):
    """
    Cleanup a company name from some of the things seen in exports.

    Parameters:
    - name(string): the name of the company from the export

    Returns
    - cleaned up company name
    """

    # remove anything from comma onwards e.g. ", PMP"
    name = name.split(',')[0].strip()

    # remove anything after and including " - "
    if " - " in name:
        name = name.split(" - ")[0].strip()

    # remove " (" and everything after (e.g., "Signify (Philips Lighting)")
    if " (" in name:
        name = name.split(" (")[0].strip()

    # remove " | blah" and everything after
    if " | " in name:
        name = name.split(" | ")[0].strip()

    # remove " / blah" and everything after
    if " / " in name:
        name = name.split(" / ")[0].strip()

    # remove common company suffixes
    suffixes = [
        " Co.", "Co", " Inc.", " Inc", " SpA", " LLC", " LLP", " LP", " Corp.", " Corp", ", INC", ", INC.", " Inc", " Inc.", " Ltd.", " Ltd", " PLC", " AG", " BV", " GmbH"
    ]
    for suffix in suffixes:
        if name.upper().endswith(suffix.upper()):
            name = name[: -len(suffix)].strip()

    # remove any non-alphabetic characters at the end
    name = re.sub(r'[^a-zA-Z]+$', '', name).strip()

    # strip leading and trailing whitespace
    name = name.strip()

    return name

def get_connected_on(field_map, row):
    """
    Retrieve the "Connected On" date from the LinkedIn export row

    Parameters:
    field_map: list of field names mapped to fields
    row: the row of data for this connection from the export

    Returns:
    Date connected in format YYYY-MM-DD
    """

    connected_on_raw = row[field_index(CONNECTIONS_CONNECTED_ON, field_map)]
    connected_on = ""

    if connected_on_raw:
        try:
            # Example: 01-Jul-25
            dt = datetime.strptime(connected_on_raw, "%d-%b-%y")
            connected_on = dt.strftime("%Y-%m-%d")
        except Exception as e:
            logging.warning(f"Could not parse connected_on date '{connected_on_raw}': {e}")
            connected_on = connected_on_raw  # fallback to original if parsing fails

    return connected_on

def get_last_name(row, field_map):
    """
    Grabs the person's last name and cleans it up
    
    Parameters:
    field_map: list of field names mapped to fields
    row: the row of data for this connection from the export

    Returns:
    Last name
    """

    # clean last name: remove anything after a comma
    last_name = row[field_index(CONNECTIONS_LAST_NAME, field_map)]
    last_name = last_name.split(',')[0].strip()
    
    # remove " PMP" and anything after it
    if " PMP" in last_name:
        last_name = last_name.split(" PMP")[0].strip()

    # Do NOT remove anything from the first non-alphabetic character onward
    # This preserves multi-word last names like "De Lima"

    last_name = last_name.strip()
    
    return last_name

def store_connections_info(people, the_config, field_map, row):
    """
    Store the connection information from a row in the `connections.csv`
    file into a Person and Organization objects.

    Parameters:
    - people: List of Person objects to which the Person will be added to.
    - the_config: Configuration object with source folder and other settings.
    - field_map: List mapping field names to their indices in the CSV row.
    - row: List representing a row from the `message_attachments.csv` file.

    Returns:
    - None
    """
    the_person = person.Person()
    the_identity = identity.Identity()

    first_name = row[field_index(CONNECTIONS_FIRST_NAME, field_map)].strip()

    # remove "Dr. " or similar titles from the start of the first name
    first_name = re.sub(r'^(Dr\.|Mr\.|Mrs\.|Ms\.|Miss|Prof\.)\s+', '', first_name, flags=re.IGNORECASE)

    # if they have an alias, keep it e.g. Catherine (Cathy) or Jose Roberto "Jobet" De Lima
    if '"' in first_name:
        # Extract alias in double quotes
        match = re.search(r'"([^"]+)"', first_name)
        if match:
            alias = match.group(1).strip()
            # Remove the alias part from the first name
            main_name = re.sub(r'"[^"]+"', '', first_name).strip()
            # Remove anything after and including ' - Bcom' or similar
            main_name = re.sub(r'\s*-\s*[Bb][Cc]om.*$', '', main_name).strip()
            # Remove degree suffixes like B.Sc., MSc, PhD, etc.
            main_name = re.sub(r'\b(B\.?Sc\.?|M\.?Sc\.?|Ph\.?D\.?|B\.?Com\.?)\b\.?', '', main_name, flags=re.IGNORECASE).strip()
            the_identity.first_name = main_name
            the_identity.alias = alias
        else:
            # Remove anything after and including ' - Bcom' or similar
            main_name = re.sub(r'\s*-\s*[Bb][Cc]om.*$', '', first_name).strip()
            # Remove degree suffixes like B.Sc., MSc, PhD, etc.
            main_name = re.sub(r'\b(B\.?Sc\.?|M\.?Sc\.?|Ph\.?D\.?|B\.?Com\.?)\b\.?', '', main_name, flags=re.IGNORECASE).strip()
            the_identity.first_name = main_name
    elif "(" in first_name and ")" in first_name:
        # Extract main name and alias in parentheses
        main_name = first_name.split("(", 1)[0].strip()
        alias = first_name.split("(", 1)[1].split(")", 1)[0].strip()
        # Remove anything after and including ' - Bcom' or similar
        main_name = re.sub(r'\s*-\s*[Bb][Cc]om.*$', '', main_name).strip()
        # Remove degree suffixes like B.Sc., MSc, PhD, etc.
        main_name = re.sub(r'\b(B\.?Sc\.?|M\.?Sc\.?|Ph\.?D\.?|B\.?Com\.?)\b\.?', '', main_name, flags=re.IGNORECASE).strip()
        the_identity.first_name = main_name
        the_identity.alias = alias
    else:
        # Remove anything after and including ' - Bcom' or similar
        main_name = re.sub(r'\s*-\s*[Bb][Cc]om.*$', '', first_name).strip()
        
        # Remove degree suffixes like B.Sc., MSc, PhD, etc.
        main_name = re.sub(r'\b(B\.?Sc\.?|M\.?Sc\.?|Ph\.?D\.?|B\.?Com\.?)\b\.?', '', main_name, flags=re.IGNORECASE).strip()
        the_identity.first_name = main_name

    the_identity.last_name = get_last_name(row, field_map)

    # Convert first and last names to title case for mixed case output
    the_identity.first_name = the_identity.first_name.title()
    the_identity.last_name = the_identity.last_name.title()

    if the_identity.first_name and the_identity.last_name:
        the_identity.full_name = the_identity.first_name + " " + the_identity.last_name
        the_identity.name = the_identity.full_name

    url = row[field_index(CONNECTIONS_URL, field_map)]
    the_person.url = url

    if not url or not (first_name or the_identity.last_name):
        return False

    # grab the last part of the URL after the last "/"
    if url and "/" in url:
        linkedin_id = url.rstrip("/").split("/")[-1]
    else:
        linkedin_id = ""

    the_person.socials.linkedin_id = linkedin_id

    company = row[field_index(CONNECTIONS_COMPANY, field_map)]
    company_name = clean_company_name(company)

    position_name = row[field_index(CONNECTIONS_POSITION, field_map)]
    the_position = position.Position()
    the_position.title = position_name
    the_position.current = True

    the_position.organization.name = company_name
    organization_slug = the_position.organization.generate_slug()
    the_position.organization.slug = organization_slug
    the_person.organizations.append(organization_slug)

    the_position.organization = organization_slug
    the_person.positions.append(the_position)

    the_person.url = url

    the_person.last_updated = datetime.now().strftime("%Y-%m-%d")
    the_person.connected_on = get_connected_on(field_map, row)
    the_person.identity = the_identity

    the_person.slug = the_person.identity.generate_slug()
    
    email_address = row[field_index(CONNECTIONS_EMAIL_ADDRESS, field_map)]
    if email_address:
            the_person.contact.email = email_address

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
        
        with open(filename, newline='', encoding='utf-8') as attachments_file:
            
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
