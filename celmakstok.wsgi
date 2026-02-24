import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import sys
import os

# Add project directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

try:
	application = create_app()
except Exception as e:
	# Log the error to a file for debugging
	with open(os.path.join(os.path.dirname(__file__), 'wsgi_error.log'), 'a', encoding='utf-8') as f:
		import traceback
		f.write('\n--- WSGI Startup Error ---\n')
		f.write(str(e) + '\n')
		f.write(traceback.format_exc() + '\n')
	raise
application = app
