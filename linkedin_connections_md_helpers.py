import os
import re
import glob
from difflib import SequenceMatcher

def find_person_by_name_or_id(name, linkedin_id, people_dir):
    """
    Fuzzy match a person by name or linkedin_id in the people_dir.
    Returns (slug, md_path) or (None, None) if not found.
    """
    # Try by linkedin_id first
    for root, dirs, files in os.walk(people_dir):
        for file in files:
            if file.endswith('.md'):
                md_path = os.path.join(root, file)
                with open(md_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if f"linkedin_id: {linkedin_id}" in content:
                        slug = os.path.basename(root)
                        return slug, md_path
    # Fuzzy match by name
    best_score = 0.0
    best_slug = None
    best_md_path = None
    for root, dirs, files in os.walk(people_dir):
        for file in files:
            if file.endswith('.md'):
                slug = os.path.basename(root)
                candidate_name = os.path.splitext(file)[0]
                score = SequenceMatcher(None, candidate_name.lower(), name.lower()).ratio()
                if score > best_score:
                    best_score = score
                    best_slug = slug
                    best_md_path = os.path.join(root, file)
    if best_score > 0.85:
        return best_slug, best_md_path
    return None, None

def parse_positions_from_body(body):
    # DEBUG: Print all lines under ## Positions
    debug_lines = []
    in_positions = False
    for line in body.splitlines():
        if line.strip() == '## Positions':
            in_positions = True
            continue
        if in_positions:
            if line.strip().startswith('## ') and line.strip() != '## Positions':
                break
            debug_lines.append(line.rstrip())
    # Now parse positions as before
    import re
    positions = []
    for line in debug_lines:
        if re.match(r'^\s*- ', line):
            positions.append(line.strip())
    # Print debug info
    print('[DEBUG] Lines under ## Positions:')
    for l in debug_lines:
        print(f'[DEBUG]   {l}')
    print(f'[DEBUG] Parsed positions: {positions}')
    return positions
    """
    Parse the ## Positions section and return a list of position bullets.
    """
    import re
    positions = []
    in_positions = False
    for line in body.splitlines():
        if line.strip() == '## Positions':
            in_positions = True
            continue
        if in_positions:
            # Stop at next section header
            if line.strip().startswith('## ') and line.strip() != '## Positions':
                break
            # Collect any line that looks like a markdown bullet (any whitespace then dash)
            if re.match(r'^\s*- ', line):
                positions.append(line.strip())
    return positions

def compare_positions(md_bullet, csv_title, csv_org):
    """
    Fuzzy match the position bullet with the CSV title/org.
    Returns a float between 0 and 1.
    """
    # Remove #current and org link
    def extract_title_org(bullet):
        # Remove #current, trailing date, and 'reported to ...'
        bullet = re.sub(r'#current', '', bullet)
        bullet = re.sub(r',? \d{4}-\d{2}(-\d{2})?', '', bullet)
        bullet = re.sub(r',? reported to .+', '', bullet, flags=re.IGNORECASE)
        bullet = bullet.strip()
        # Remove '- ' at start
        if bullet.startswith('- '):
            bullet = bullet[2:]
        # Split on ', [[' to separate title and org
        if ', [[' in bullet:
            title, org = bullet.split(', [[', 1)
            org = org.split(']]')[0]
        else:
            # Fallback: split on last comma
            parts = bullet.rsplit(',', 1)
            if len(parts) == 2:
                title, org = parts[0], parts[1]
            else:
                title, org = bullet, ''
        title = title.replace('&', 'and').strip().lower()
        org = org.replace('&', 'and').strip().lower()
        return title, org

    md_title, md_org = extract_title_org(md_bullet)
    csv_title_clean = csv_title.replace('&', 'and').strip().lower()
    csv_org_clean = csv_org.replace('&', 'and').strip().lower()

    # Fuzzy match both title and org, average the scores
    title_score = SequenceMatcher(None, md_title, csv_title_clean).ratio()
    org_score = SequenceMatcher(None, md_org, csv_org_clean).ratio() if csv_org_clean else 1.0
    return (title_score + org_score) / 2
