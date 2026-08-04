import requests

def probe():
    urls = [
        "http://192.168.18.49:8000/",
        "http://192.168.18.49:8000/api/telemetry?inverter=all",
        "http://100.97.146.42:8000/api/telemetry?inverter=all"
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=3)
            print(f"URL: {url} | Status: {r.status_code}")
            print(f"  Response: {r.text[:200]}")
        except Exception as e:
            print(f"URL: {url} | Error: {e}")

if __name__ == "__main__":
    probe()
