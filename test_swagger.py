import requests

# Let's test if the flask app is running and /apidocs works
try:
    resp = requests.get('http://127.0.0.1:5000/apidocs/')
    if resp.status_code == 200:
        print("Success: /apidocs/ is accessible.")
        print(resp.text[:200])
    else:
        print("Failed with status code:", resp.status_code)
except Exception as e:
    print("Error:", e)
