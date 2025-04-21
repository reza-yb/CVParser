import requests
import json
import argparse
import time

PROTOCOL = "https"
HOSTNAME = "mathgenealogy.org"
EMAIL = "YOUR@EMAIL"  # Update with your email
PASSWORD = "YOUR PASSWORD"        # Update with your password
PORT = "8000"

def getlogin():
    return {'email': EMAIL, 'password': PASSWORD}

def login(authdata):
    r = requests.post(f"{PROTOCOL}://{HOSTNAME}:{PORT}/login", data=authdata)
    if r.ok:
        token = r.json()
        r.close()
        return token
    else:
        r.close()
        raise RuntimeError("Failed to authenticate")

def doquery(endpoint, token, params):
    headers = {'x-access-token': token['token']}
    url = f"{PROTOCOL}://{HOSTNAME}:{PORT}{endpoint}"
    r = requests.get(url, headers=headers, params=params)
    if r.ok:
        result = r.text
        r.close()
        return result
    else:
        r.close()
        raise RuntimeError(f"Error executing query: {r.status_code} - {r.text}")

def search_by_name(token, name):
    endpoint = '/api/v2/MGP/search'
    
    # Try different search strategies
    search_strategies = []
    name_parts = name.strip().split()
    
    # Strategy 1: Use exact name as family_name
    if len(name_parts) == 1:
        search_strategies.append({'family_name': name})
    
    # Strategy 2: Last part as family name, rest as given name
    if len(name_parts) > 1:
        family_name = name_parts[-1]
        given_name = ' '.join(name_parts[:-1])
        search_strategies.append({
            'family_name': family_name,
            'given_name': given_name
        })
    
    # Strategy 3: First part as given name, rest as family name
    if len(name_parts) > 1:
        given_name = name_parts[0]
        family_name = ' '.join(name_parts[1:])
        search_strategies.append({
            'family_name': family_name,
            'given_name': given_name
        })
    
    # Try each strategy until we get results
    all_results = []
    for strategy in search_strategies:
        try:
            search_results = json.loads(doquery(endpoint, token, strategy))
            if search_results:
                all_results.extend(search_results)
                # Remove duplicates
                all_results = list(dict.fromkeys(all_results))
        except Exception as e:
            print(f"Search error with parameters {strategy}: {e}")
    
    return all_results

def fetch_person_details(token, person_id):
    endpoint = f"/api/v2/MGP/acad"
    querydata = {'id': person_id}
    person_data = json.loads(doquery(endpoint, token, querydata))
    return person_data['MGP_academic']

def display_person_info(person_details):
    degrees = person_details.get('student_data', {}).get('degrees', [{}])[0]
    
    print(f"ID: {person_details['ID']}")
    print(f"Name: {person_details.get('given_name', '')} {person_details.get('family_name', '')}")
    
    if 'degree_msc' in degrees:
        print(f"Degree MSC: {degrees.get('degree_msc', '')}")
    
    if 'degree_year' in degrees:
        print(f"Year: {degrees.get('degree_year', '')}")
    
    if 'schools' in degrees:
        print(f"School: {', '.join(degrees.get('schools', []))}")
    
    if 'thesis_title' in degrees:
        print(f"Thesis: {degrees.get('thesis_title', '')}")
    
    if degrees.get('advised by'):
        print("Advisors:")
        for advisor_id, advisor_name in degrees['advised by'].items():
            print(f"  - {advisor_name} (ID: {advisor_id})")
    
    print("-" * 50)

def get_advisor_chain(token, person_id, processed_ids=None, indent=0, max_depth=10):
    """Recursively fetch and display the advisor chain for a mathematician."""
    if processed_ids is None:
        processed_ids = set()
    
    # Avoid cycles in the advisor chain or exceeding maximum depth
    if person_id in processed_ids or indent > max_depth:
        if indent > max_depth:
            print(f"{' ' * indent * 4}(Max depth reached)")
        return
    
    # Skip special ID '0' which represents 'Unknown'
    if person_id == "0" or person_id == 0:
        print(f"{' ' * indent * 4}→ Unknown (No further information available)")
        return
    
    processed_ids.add(person_id)
    indent_str = "    " * indent
    
    try:
        person = fetch_person_details(token, person_id)
        
        # Handle missing or incomplete data
        if 'student_data' not in person or 'degrees' not in person.get('student_data', {}) or not person.get('student_data', {}).get('degrees', []):
            name = f"{person.get('given_name', '')} {person.get('family_name', '')}"
            print(f"{indent_str}→ {name} (No degree information available)")
            return
            
        degrees = person.get('student_data', {}).get('degrees', [{}])[0]
        
        name = f"{person.get('given_name', '')} {person.get('family_name', '')}"
        year = degrees.get('degree_year', 'Unknown')
        school = ', '.join(degrees.get('schools', ['Unknown']))
        
        print(f"{indent_str}→ {name} ({year}, {school})")
        
        # Get advisors
        advisors = degrees.get('advised by', {})
        if advisors:
            for advisor_id, advisor_name in advisors.items():
                # Skip 'Unknown' advisors
                if advisor_id == "0" or advisor_name.lower() == "unknown":
                    print(f"{indent_str}    → {advisor_name} (No further information available)")
                    continue
                
                # Add a small delay to avoid overwhelming the API
                time.sleep(0.5)
                get_advisor_chain(token, advisor_id, processed_ids, indent + 1, max_depth)
        else:
            print(f"{indent_str}    (No further advisors recorded)")
    
    except Exception as e:
        print(f"{indent_str}Error fetching data: {str(e).split(chr(10))[0]}")

def main():
    # Hardcoded search for Milton Friedman
    search_name = "Milton Friedman"
    show_detailed_info = False  # Set to True if you want detailed information
    
    # Check if credentials are set
    if not EMAIL or not PASSWORD:
        print("Please set your EMAIL and PASSWORD in the script before running")
        return
    
    try:
        print(f"Searching for: {search_name}")
        authdata = getlogin()
        token = login(authdata)
        
        results = search_by_name(token, search_name)
        
        if not results:
            print(f"No results found for '{search_name}'")
            return
        
        print(f"Found {len(results)} mathematicians matching '{search_name}':")
        print("=" * 60)
        
        for person_id in results:
            try:
                person_details = fetch_person_details(token, person_id)
                
                # Display basic information
                name = f"{person_details.get('given_name', '')} {person_details.get('family_name', '')}"
                degrees = person_details.get('student_data', {}).get('degrees', [{}])[0]
                year = degrees.get('degree_year', 'Unknown')
                school = ', '.join(degrees.get('schools', ['Unknown']))
                
                print(f"Academic Genealogy for {name} (ID: {person_details['ID']})")
                print(f"Degree earned in {year} at {school}")
                
                if degrees.get('thesis_title'):
                    print(f"Thesis: {degrees.get('thesis_title')}")
                
                print("\nAdvisor Chain:")
                
                # Display the advisor chain
                get_advisor_chain(token, person_id)
                
                # Optionally display detailed info
                if show_detailed_info:
                    print("\nDetailed Information:")
                    display_person_info(person_details)
                
                print("=" * 60)
            except Exception as e:
                print(f"Error fetching details for ID {person_id}: {e}")
                print("=" * 60)
    
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    main() 
