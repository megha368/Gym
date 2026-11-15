from config.settings import PORT
from web import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT) # host = 0.0.0.0 means we accept visitors from any computer



