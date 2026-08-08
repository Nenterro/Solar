import urllib.request, json

url = 'http://localhost:8000/api/inverter_settings/update'
data = json.dumps({'inverter': 'inv3', 'command': 'PBCV52.0'}).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as resp:
        print('API Response:', resp.read().decode('utf-8'))
except Exception as e:
    print('Error:', e)
