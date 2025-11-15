from app import create_app
# [POPRAWKA] Importuj bibliotekę dotenv
# BŁĄD był tutaj: "from .env import load_dotenv"
# Poprawny import to nazwa biblioteki: "dotenv"
from dotenv import load_dotenv 

# [POPRAWKA] Załaduj plik .env ZANIM stworzysz aplikację
load_dotenv()

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)