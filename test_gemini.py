import os
from google import genai

# Uses Vertex AI with your gcloud login (application-default credentials); no API key needed.
client = genai.Client(
    vertexai=True,
    project=os.environ.get("GOOGLE_CLOUD_PROJECT", "dazzling-lodge-511607-m0"),
    location="us-central1",
)
resp = client.models.generate_content(
    model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
    contents="Say hello in one short sentence.",
)
print(resp.text)
