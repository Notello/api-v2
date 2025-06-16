import os
from flask_app import create_app

app = create_app()

if __name__ == '__main__':
    # allow DO (or any host) to override the port
    port = int(os.environ.get('PORT', 5000))
    # bind to 0.0.0.0 so the container IP (10.x.x.x) is listening, not just localhost
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
