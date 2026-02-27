import requests

# We create a session to hold cookies
session = requests.Session()

# The target server URL (assuming it runs on localhost:5000)
URL = "http://localhost:5000"

try:
    # We will try to login
    # Wait, we don't know the exact username of the 'Genel' user.
    # Let's write a small script to query the database and get the username first, locally.
    pass
except Exception as e:
    print("Error:", e)
