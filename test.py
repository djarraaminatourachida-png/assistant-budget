import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
cle = os.getenv("GEMINI_API_KEY")
print("Clé trouvée :", cle is not None)

client = genai.Client(api_key=cle)

try:
    reponse = client.models.generate_content(
        model="gemini-3.8-flash",
        contents="Dis bonjour en une phrase, en français."
    )
    print(reponse.text)
except Exception as e:
    print("ERREUR :", e)