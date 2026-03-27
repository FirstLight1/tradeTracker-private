from sys import argv
import requests
import json

def testAddAuction(payload_path):
    headers = {
        'Content-Type': 'application/json'
    }
    
    # Load the JSON payload from file
    with open(payload_path, 'r') as f:
        payload = json.load(f)
    
    response = requests.post("http://127.0.0.1:5000/add", json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")


if __name__ == '__main__':
    payload_path = argv[1]
    testAddAuction(payload_path)
