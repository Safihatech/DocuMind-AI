import requests, json
url='http://127.0.0.1:8001/qa/query'
q={'query':'Summarize the uploaded document in one sentence.'}
print('POST',url,q)
r=requests.post(url,json=q,timeout=60)
print('status',r.status_code)
try:
    print(json.dumps(r.json(),indent=2))
except Exception:
    print(r.text)
