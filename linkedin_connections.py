import sys
import connections

sys.path.insert(1, '../message_md/')
import markdown
import message_md
import config
import markdown

the_config = config.Config()
the_people = []

# main

if message_md.setup(the_config, markdown.YAML_SERVICE_SIGNAL, False):
    connections.parse_connections_file(the_people, the_config)

    for person in the_people:
        print(person.identity.name + ", " + person.slug + ", " + str(person.organizations))