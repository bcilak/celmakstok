import sys
import os
import json
from dotenv import load_dotenv

sys.path.append('/Users/emin/ProgrammingProjects/celmak/celmakstok')
load_dotenv('/Users/emin/ProgrammingProjects/celmak/celmakstok/.env')

from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        print("Admin user not found!")
        sys.exit(1)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin.id)
        sess['_fresh'] = True

    # Test query
    query = "10 tane 165 tamburlu maliyeti ne olur?"
    print(f"Sending POST request for query: '{query}'...")
    response = client.post('/reports/ai-assistant/ask', json={'query': query, 'history': []})
    print("Status Code:", response.status_code)
    resp_data = response.get_json()
    print("Source:", resp_data.get('source'))
    print("Response JSON:\n", json.dumps(resp_data, indent=2, ensure_ascii=False))
