
import requests
import json
import pandas as pd
import concurrent.futures
import re

from tqdm import tqdm

PROTOCOL = "https"
HOSTNAME = "mathgenealogy.org"
EMAIL = ""
PASSWORD = ""
PORT = "8000"
START_YEAR = 1901
END_YEAR = 2025

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
    r = requests.get(f"{PROTOCOL}://{HOSTNAME}:{PORT}{endpoint}", headers=headers, params=params)
    if r.ok:
        result = r.text
        r.close()
        return result
    else:
        r.close()
        raise RuntimeError("Error executing query")

def fetch_person_details(token, person_id):
    endpoint = f"/api/v2/MGP/acad"
    querydata = {'id': person_id}
    person_data = json.loads(doquery(endpoint, token, querydata))
    return person_data['MGP_academic']

def sanitize_string(value):
    if isinstance(value, str):
        return re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
    return value

def process_person(person, token):
    person_details = fetch_person_details(token, person)

    degrees = person_details['student_data']['degrees'][0]
    person_dict = {
        'ID': sanitize_string(person_details['ID']),
        'Family Name': sanitize_string(person_details['family_name']),
        'Given Name': sanitize_string(person_details['given_name']),
        'Degree MSC': sanitize_string(degrees.get('degree_msc', '')),
        'Degree Year': sanitize_string(degrees.get('degree_year', '')),
        'School': sanitize_string(', '.join(degrees.get('schools', []))),
        'Thesis Title': sanitize_string(degrees.get('thesis_title', '')),
    }

    edges = []
    if degrees.get('advised by'):
        for advisor_id, advisor_name in degrees['advised by'].items():
            edge_dict = {
                'Advisor ID': sanitize_string(advisor_id),
                'Advisee ID': sanitize_string(person_details['ID'])
            }
            edges.append(edge_dict)

    return person_dict, edges

if __name__ == '__main__':
    authdata = getlogin()
    token = login(authdata)

    all_person_details_list = []
    all_edges_list = []

    for year in range(START_YEAR, END_YEAR):
        print(f"Fetching data for year: {year}")

        current_year_nodes = []
        current_year_edges = []

        searchparams = {
            'year': year
        }
        endpoint = '/api/v2/MGP/search'
        search_results = json.loads(doquery(endpoint, token, searchparams))

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(process_person, person, token): person for person in search_results}

            for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Processing people"):
                try:
                    person_dict, edges = future.result()

                    current_year_nodes.append(person_dict)
                    all_person_details_list.append(person_dict)

                    current_year_edges.extend(edges)
                    all_edges_list.extend(edges)
                except Exception as exc:
                    print(f"An error occurred: {exc}")

        node_df = pd.DataFrame(current_year_nodes)
        edge_df = pd.DataFrame(current_year_edges)

        node_filename = f'nodes_{year}.xlsx'
        edge_filename = f'edges_{year}.xlsx'
        node_df.to_excel(node_filename, index=False)
        edge_df.to_excel(edge_filename, index=False)

        print(f"Saved nodes and edges for year {year} to {node_filename} and {edge_filename}")

    final_node_df = pd.DataFrame(all_person_details_list)
    final_edge_df = pd.DataFrame(all_edges_list)

    final_node_df.to_excel('final_nodes.xlsx', index=False)
    final_edge_df.to_excel('final_edges.xlsx', index=False)

    print(f"Saved final node file to 'final_nodes.xlsx' and final edge file to 'final_edges.xlsx'")