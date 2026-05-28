# linkedin_md

## Requirements

This project requires Python 3 and the PyYAML package:

```sh
pip install pyyaml
```

If you see `ModuleNotFoundError: No module named 'yaml'`, install PyYAML as shown above.

This tool takes the CSV output file from the [LinkedIn export](docs/linkedin_export.md) and generates a set of Markdown files on your filesystem. 

## message_md dependency

The code in this repo relies heavily on my [message_md](https://github.com/thephm/message_md) classes which contain generic `Message`, `Person`, `Group` and other classes and the methods to convert messages to Markdown files. Be sure to read the [README](https://github.com/thephm/message_md/blob/main/README.md) and the configuration [guide](https://github.com/thephm/message_md/blob/main/docs/guide.md) for that repo first. 

## Limitations

1. Doesn't handle attachments

## linkedin_connections_md.py

This script parses a LinkedIn connections export CSV file and updates each person's Markdown profile with their current position.

**Features:**
- For each person in the CSV, finds the corresponding Markdown profile by name or LinkedIn ID (from the profile URL).
- Checks the "## Positions" section in the Markdown file and compares the current position (marked with `#current`) to the CSV data.
- If the position is unchanged, outputs `[slug]: no change`.
- If different, removes `#current` from the old position, adds a new bullet for the new position with `#current`, and outputs messages about the changes.
- If no profile is found, outputs `[name] [LinkedIn profile URL] not found`.

**Usage:**
1. Place your LinkedIn connections export CSV in the project directory and set the `CSV_FILE` variable in the script.
2. Set the `PEOPLE_DIR` variable to the directory containing your person Markdown files.
3. Run the script:
	```sh
	python linkedin_connections_md.py
	```
4. Review the output for changes and not-found profiles.

See the script for more details and adjust as needed for your workflow.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE.md) file for details.