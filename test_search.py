import requests

r = requests.post('http://localhost:5000/api/search', json={'query':'arabe','mode':'hybrid'})
print('Status:', r.status_code)

results = r.json().get('results', [])
print(f'Found {len(results)} results')
print()
for i, result in enumerate(results[:5], 1):
    print(f"  {i}. {result['chunk_id']} - {result['subject']} (Grade {result['grade']}) - Score: {result['score']}%")
