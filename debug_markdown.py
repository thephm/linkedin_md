#!/usr/bin/env python3

import sys
sys.path.insert(1, '../message_md/')
import message_md
import config
import markdown
sys.path.insert(1, '../hal/')
import person
import os

# Setup config same as main script
the_messages = []
the_reactions = []
the_config = config.Config()

if message_md.setup(the_config, markdown.YAML_SERVICE_LINKEDIN):
    # Load messages
    from linkedin_md import load_messages
    dest_file = "../../messages/archive/linkedin_2025-09-29_07-09-06.csv"
    count = load_messages(dest_file, the_messages, the_reactions, the_config)
    print(f"Loaded {count} messages, {len(the_messages)} valid messages")
    
    # Add messages to people (same as get_markdown does)
    import message
    message.add_messages(the_messages, the_config)
    
    # Check which people have messages
    people_with_messages = [p for p in the_config.people if hasattr(p, 'messages') and len(p.messages) > 0]
    print(f"\nPeople with messages: {len(people_with_messages)}")
    
    # Try the markdown generation loop with debug
    for i, the_person in enumerate(the_config.people):
        if hasattr(the_person, 'messages') and len(the_person.messages) > 0:
            print(f"\nProcessing person {the_person.slug} with {len(the_person.messages)} messages")
            print(f"  ignore flag: {the_person.ignore}")
            
            if not the_person.ignore:
                folder = os.path.join(the_config.people_folder, the_person.slug)
                print(f"  folder: {folder}")
                
                # Check if folder creation works
                try:
                    os.makedirs(folder, exist_ok=True)
                    print(f"  folder created successfully")
                    
                    # Try calling create_markdown_files
                    print(f"  calling create_markdown_files...")
                    markdown.create_markdown_files(the_person, folder, the_config)
                    print(f"  create_markdown_files completed")
                    
                except Exception as e:
                    print(f"  ERROR: {e}")
            
            # Only process first few to avoid spam
            if i > 5:
                print("  (stopping after first few people for debugging)")
                break
                
    print("\nDone!")