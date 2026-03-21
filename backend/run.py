import os
import uvicorn
from pyngrok import ngrok, conf
from dotenv import load_dotenv

load_dotenv()

ngrok_token = os.environ.get("NGROK_AUTHTOKEN")
if ngrok_token:
    conf.get_default().auth_token = ngrok_token

if __name__ == "__main__":
    ngrok.kill()

    port = 8000
    public_url = ngrok.connect(port).public_url

    print("\n" + "="*50)
    print(f"ngrok public URL: {public_url}")
    print(f"Webhook URL to paste in GitHub: {public_url}/webhook")
    print("="*50 + "\n")

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
