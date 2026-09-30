from flask import Flask 
from config.settings import PORT 
from database.database import init_db

app = Flask(__name__) # var app is now the website

@app.route("/health")
def health():
    return {"status": "ok"} # if server replies with status: ok, the system knows the app is healthy 

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT) # host = 0.0.0.0 means we accept visitors from any computer

init_db()

