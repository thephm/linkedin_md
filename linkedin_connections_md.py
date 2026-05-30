def main():
    parser = argparse.ArgumentParser(description="Update LinkedIn Markdown profiles from export CSV.")
    parser.add_argument('-c', '--config', dest='config_dir', default=DEFAULT_CONFIG_DIR, help='Config folder (not used yet)')
    parser.add_argument('-s', '--source', dest='people_dir', default=DEFAULT_PEOPLE_DIR, help='Source folder for person Markdown files')
    parser.add_argument('-f', '--file', dest='csv_file', default=DEFAULT_CSV_FILE, help='Source LinkedIn CSV file')
    parser.add_argument('-o', '--output', dest='output_dir', default=None, help='Output folder for updated Markdown files (default: same as source)')
    parser.add_argument('-x', '--max', dest='max_people', type=int, default=None, help='Max people to update')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='Enable debug/verbose output')
    args = parser.parse_args()

    people_dir = args.people_dir
    csv_file = args.csv_file or DEFAULT_CSV_FILE
    output_dir = args.output_dir or people_dir
    max_people = args.max_people
    debug = args.debug
    # config_dir = args.config_dir  # Not used yet

    if not people_dir or not os.path.isdir(people_dir):
        print(f"ERROR: Source folder for People Markdown files not found: {people_dir}\nSpecify the folder containing your People Markdown files with -s or --source.")
        sys.exit(1)

    updated_count = 0
    processed_count = 0
    not_found_count = 0
    if not os.path.isfile(csv_file):
        print(f"ERROR: CSV file not found: {csv_file}\nSpecify the correct folder with -f or --file, or provide the full path to the file.")
        sys.exit(1)
    with open(csv_file, 'r', encoding='utf-8') as f:
        # Skip lines until we find the header
        while True:
            header = f.readline()
            if not header:
                print("ERROR: Could not find CSV header line starting with 'First Name'.")
                sys.exit(1)
            if header.strip().startswith('First Name'):
                break
        header = header.strip().replace('\r', '').replace('\n', '')
        fieldnames = [h.strip() for h in header.split(',')]
        # Read the rest of the lines as data
        data_lines = list(f)
        reader = csv.DictReader(data_lines, fieldnames=fieldnames)
        if debug:
            print(f"[DEBUG] CSV fieldnames: {fieldnames}")
        for row in reader:
            processed_count += 1
            if debug:
                print(f"[DEBUG] Raw CSV row: {row}")
            import re
            first_name = row.get('First Name', '').strip()
            last_name = row.get('Last Name', '').strip()
            # Remove credentials after comma, parenthetical pronouns, or trailing uppercase credentials
            last_name = re.sub(r',.*', '', last_name).strip()
            last_name = re.sub(r'\(.*?\)', '', last_name).strip()
            last_name = re.sub(r'\s+([A-Z][A-Z\.\-/ ]+)$', '', last_name).strip()
            name = f"{first_name} {last_name}".strip()
            linkedin_url = row.get('URL', '').strip()
            linkedin_id = get_linkedin_id_from_url(linkedin_url)
            csv_title = row.get('Position', '').strip()
            csv_org = row.get('Company', '').strip()
            if debug:
                print(f"[DEBUG] Extracted: name='{name}', linkedin_url='{linkedin_url}', linkedin_id='{linkedin_id}', title='{csv_title}', org='{csv_org}'")

            slug, md_path = find_person_by_name_or_id(name, linkedin_id, people_dir)
            if not slug:
                print(f"{name} {linkedin_url} not found")
                not_found_count += 1
                if max_people is not None and processed_count >= max_people:
                    print(f"Max people processed ({max_people}), stopping.")
                    break
                continue
            if debug:
                print(f"Found profile slug: {slug}, file: {md_path}")
            frontmatter, body = load_markdown_profile_from_path(md_path)
            if not frontmatter or not body:
                print(f"{slug}: profile not loaded")
                if max_people is not None and processed_count >= max_people:
                    print(f"Max people processed ({max_people}), stopping.")
                    break
                continue

            # --- Update frontmatter fields ---
            updated_fields = []
            connected_on_csv = row.get('Connected On', '').strip()
            connected_on_fmt = None
            if connected_on_csv:
                import datetime
                try:
                    connected_on_dt = datetime.datetime.strptime(connected_on_csv, "%d %b %Y")
                    connected_on_fmt = connected_on_dt.strftime("%Y-%m-%d")
                except Exception as e:
                    if debug:
                        print(f"Could not parse Connected On date '{connected_on_csv}': {e}")
            if connected_on_fmt and not frontmatter.get('connected_on'):
                frontmatter['connected_on'] = connected_on_fmt
                updated_fields.append(f"connected_on={connected_on_fmt}")
                if debug:
                    print(f"Set connected_on: {connected_on_fmt}")

            # 2. Title
            if csv_title and frontmatter.get('title') != csv_title:
                frontmatter['title'] = csv_title
                updated_fields.append(f"title={csv_title}")
                if debug:
                    print(f"Set title: {csv_title}")

            positions = parse_positions_from_body(body)
            # Track if positions were updated (by checking for added/removed #current)
            positions_updated = False
            # Find the best fuzzy match for the new CSV position
            best_score = 0.0
            best_idx = None
            current_idx = None
            if debug:
                print(f"[DEBUG] Comparing CSV position '{csv_title}, {csv_org}' to all markdown positions:")
            # Prefer the position with #current for matching
            for idx, bullet in enumerate(positions):
                if '#current' in bullet:
                    current_idx = idx
                    score = compare_positions(bullet, csv_title, csv_org)
                    if debug:
                        print(f"[DEBUG]   #current Position {idx}: '{bullet}' => score={score}")
                    best_score = score
                    best_idx = idx
                    break
            # If no #current, compare to all positions and pick the best match
            if current_idx is None:
                for idx, bullet in enumerate(positions):
                    score = compare_positions(bullet, csv_title, csv_org)
                    if debug:
                        print(f"[DEBUG]   Position {idx}: '{bullet}' => score={score}")
                    if score > best_score:
                        best_score = score
                        best_idx = idx
            if debug:
                print(f"[DEBUG] Best match idx={best_idx}, score={best_score}")

            if best_score >= 0.7:
                # Update the title of the matched position, keep everything else
                import re
                old_bullet = positions[best_idx]
                # Replace the title (before first comma or [[) with the new title
                def replace_title(bullet, new_title):
                    # Find start of org or end
                    m = re.match(r'(- )?[^,\[]+', bullet)
                    if m:
                        rest = bullet[m.end():]
                        return f"- {csv_title}{rest}"
                    else:
                        return f"- {csv_title}"

                new_bullet = replace_title(old_bullet, csv_title)
                # Ensure #current is present
                if '#current' not in new_bullet:
                    new_bullet = new_bullet.rstrip() + ' #current'
                positions[best_idx] = new_bullet
                # Remove #current from any other position
                for idx2, bullet2 in enumerate(positions):
                    if idx2 != best_idx and '#current' in bullet2:
                        positions[idx2] = bullet2.replace(' #current', '')
                        print(f'{slug}: removed #current on position "{bullet2}"')
                        positions_updated = True
                print(f'{slug}: updated title and #current on position "{positions[best_idx]}"')
                positions_updated = True
                # Rebuild body
                new_body_lines = []
                lines = body.splitlines()
                i = 0
                while i < len(lines):
                    line = lines[i]
                    if line.strip() == '## Positions':
                        new_body_lines.append(line)
                        new_body_lines.append('')  # blank line after header
                        # Skip all lines until next section or end
                        i += 1
                        while i < len(lines):
                            next_line = lines[i]
                            if next_line.strip().startswith('## ') and next_line.strip() != '## Positions':
                                break
                            i += 1
                        # Insert updated positions
                        new_body_lines.extend(positions)
                        # Ensure exactly one blank line after positions before next section
                        if len(new_body_lines) == 0 or new_body_lines[-1].strip() != '':
                            new_body_lines.append('')
                        # If next line is a section header, do not add extra blank lines
                        continue
                    new_body_lines.append(line)
                    i += 1
                new_body = '\n'.join(new_body_lines)
                save_markdown_profile(md_path, frontmatter, new_body)
                updated_count += 1
                if updated_fields or positions_updated:
                    print(f"{slug}: updated fields: {', '.join(updated_fields) if updated_fields else ''}{' (positions updated)' if positions_updated else ''}")
                else:
                    print(f"{slug}: no change")
                if debug:
                    print(f"Updated profile for {slug}")
                if max_people is not None and processed_count >= max_people:
                    print(f"Max people processed ({max_people}), stopping.")
                    break
                continue
            # If no good match, add a new current position
            for idx2, bullet2 in enumerate(positions):
                if '#current' in bullet2:
                    old_bullet = positions[idx2]
                    positions[idx2] = bullet2.replace(' #current', '')
                    print(f'{slug}: removed #current on position "{old_bullet}"')
                    positions_updated = True
            new_bullet = f"- {csv_title}, [[{csv_org}]] #current"
            positions.append(new_bullet)
            print(f'{slug}: added position {new_bullet}')
            positions_updated = True
            # Rebuild body
            new_body_lines = []
            lines = body.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i]
                if line.strip() == '## Positions':
                    new_body_lines.append(line)
                    new_body_lines.append('')  # blank line after header
                    # Skip all lines until next section or end
                    i += 1
                    while i < len(lines):
                        next_line = lines[i]
                        if next_line.strip().startswith('## ') and next_line.strip() != '## Positions':
                            break
                        i += 1
                    # Insert updated positions
                    new_body_lines.extend(positions)
                    # Ensure exactly one blank line after positions before next section
                    if len(new_body_lines) == 0 or new_body_lines[-1].strip() != '':
                        new_body_lines.append('')
                    # If next line is a section header, do not add extra blank lines
                    continue
                new_body_lines.append(line)
                i += 1
            new_body = '\n'.join(new_body_lines)
            save_markdown_profile(md_path, frontmatter, new_body)
            updated_count += 1
            # Output what was updated
            if updated_fields or positions_updated:
                print(f"{slug}: updated fields: {', '.join(updated_fields) if updated_fields else ''}{' (positions updated)' if positions_updated else ''}")
            else:
                print(f"{slug}: no change")
            if debug:
                print(f"Updated profile for {slug}")
            if max_people is not None and processed_count >= max_people:
                print(f"Max people processed ({max_people}), stopping.")
                break
            if debug:
                print(f"Found profile slug: {slug}, file: {md_path}")
            frontmatter, body = load_markdown_profile_from_path(md_path)
            if not frontmatter or not body:
                print(f"{slug}: profile not loaded")
                if max_people is not None and processed_count >= max_people:
                    print(f"Max people processed ({max_people}), stopping.")
                    break
                continue

            # --- Update frontmatter fields ---
            # 1. Connected On
            connected_on_csv = row.get('Connected On', '').strip()
            connected_on_fmt = None
            if connected_on_csv:
                import datetime
                try:
                    connected_on_dt = datetime.datetime.strptime(connected_on_csv, "%d %b %Y")
                    connected_on_fmt = connected_on_dt.strftime("%Y-%m-%d")
                except Exception as e:
                    if debug:
                        print(f"Could not parse Connected On date '{connected_on_csv}': {e}")
            if connected_on_fmt and not frontmatter.get('connected_on'):
                frontmatter['connected_on'] = connected_on_fmt
                if debug:
                    print(f"Set connected_on: {connected_on_fmt}")

            # 2. Title
            if csv_title:
                frontmatter['title'] = csv_title
                if debug:
                    print(f"Set title: {csv_title}")

            positions = parse_positions_from_body(body)
            if max_people is not None and processed_count >= max_people:
                print(f"Max people processed ({max_people}), stopping.")
                break


import os
import csv
import glob
import re
import sys
import yaml
import argparse
from collections import OrderedDict
from linkedin_connections_md_helpers import find_person_by_name_or_id, parse_positions_from_body, compare_positions

# Insert path to hal/person code
sys.path.insert(1, '../hal/')
import person


"""
Configuration section: defines default directories and files for the LinkedIn Markdown sync script.
"""

# Defaults (can be overridden by CLI)
DEFAULT_PEOPLE_DIR = "people/"
DEFAULT_CSV_FILE = "Connections.csv"
DEFAULT_OUTPUT_DIR = None  # If not set, use source folder
DEFAULT_CONFIG_DIR = None


"""
Helper functions for slugifying names, extracting LinkedIn IDs, and loading/saving Markdown profiles.
"""
def slugify(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

def get_linkedin_id_from_url(url):
    if not url:
        return ''
    return url.rstrip('/').split('/')[-1]


def load_markdown_profile(slug, people_dir):
    md_path = os.path.join(people_dir, f"{slug}.md")
    if not os.path.exists(md_path):
        return None, None
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Split frontmatter and body
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            frontmatter = yaml.load(parts[1], Loader=yaml.loader.SafeLoader)
            # If not OrderedDict, convert to one
            if not isinstance(frontmatter, OrderedDict):
                frontmatter = OrderedDict(frontmatter)
            body = parts[2].strip()
            return frontmatter, body
    return None, content


def save_markdown_profile(md_path, frontmatter, body):
    print(f"[DEBUG] Writing updated profile to: {md_path}")
    """
    Preserve all original fields, including empty ones, and only update/add as needed.
    """
    clean_frontmatter = OrderedDict(frontmatter)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('---\n')
        for k, v in clean_frontmatter.items():
            if k == 'tags' and isinstance(v, list):
                f.write('tags:\n')
                for tag in v:
                    f.write(f'  - {tag}\n')
            elif k == 'organizations' and isinstance(v, list):
                f.write('organizations:\n')
                for org in v:
                    f.write(f'  - {org}\n')
            elif v is None or v == '' or v == [] or v == {}:
                f.write(f'{k}:\n')
            elif isinstance(v, str) and re.match(r'^[A-Za-z0-9_\-:. ]+$', v):
                # Write simple strings (like dates) without quotes
                f.write(f'{k}: {v}\n')
            else:
                # Write other fields as YAML scalars
                yaml.dump({k: v}, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
        f.write('---\n\n')
        f.write(body.strip() + '\n')




    """
    Helper to load markdown from a specific path.
    """
def load_markdown_profile_from_path(md_path):
    if not os.path.exists(md_path):
        return None, None
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            frontmatter = yaml.safe_load(parts[1])
            body = parts[2].strip()
            return frontmatter, body
    return None, content

if __name__ == "__main__":
    main()
