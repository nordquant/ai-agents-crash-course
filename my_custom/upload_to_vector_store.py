from openai import OpenAI

import requests
import dotenv
import os

dotenv.load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=API_KEY)
# 1. Create a new vector store
vector_store = client.vector_stores.create(
   name="MyVectorStore"
)
print("Vector Store created:", vector_store.id)
# 2. Upload your .txt file
file = client.files.create(
   file=open("./questions_output.txt", "rb"),
   purpose="assistants"
)
print("File uploaded:", file.id)
# 3. Attach file to the vector store (starts ingestion)
client.vector_stores.files.create(
   vector_store_id= 
#    "vs_692d7027ebdc81918bd82062a49ab9cc",
   vector_store.id,
   file_id=file.id,
)
print("File added to vector store.")