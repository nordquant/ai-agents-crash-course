# import requests
# import dotenv
# import os

# dotenv.load_dotenv()

# # Replace with your OpenAI API key
# API_KEY = os.getenv("OPENAI_API_KEY")
# BASE_URL = "https://api.openai.com/v1"

# # Step 1: Upload file to OpenAI
# def upload_file(file_path):
#     if not os.path.exists(file_path):
#         raise FileNotFoundError(f"File not found: {file_path}")

#     url = f"{BASE_URL}/uploads"
#     headers = {
#         "Authorization": f"Bearer {API_KEY}",
#         "mime_type": "text/jsonl"
#     }
#     with open(file_path, "rb") as f:
#         files = {"file": f}
#         data = {"purpose": "vector_store"}  # Required field
#         response = requests.post(url, headers=headers, files=files, data=data)
#         response.raise_for_status()
#         file_id = response.json()["id"]
#         print(f"✅ File uploaded: {file_id}")
#         return file_id

# # Step 2: Create a Vector Store
# def create_vector_store(name="MyDocsStore"):
#     url = f"{BASE_URL}/vector_stores"
#     headers = {
#         "Authorization": f"Bearer {API_KEY}",
#         "Content-Type": "application/json"
#     }
#     data = {"name": name}
#     response = requests.post(url, headers=headers, json=data)
#     response.raise_for_status()
#     store_id = response.json()["id"]
#     print(f"✅ Vector Store created: {store_id}")
#     return store_id

# # Step 3: Attach file to Vector Store
# def attach_file_to_vector_store(store_id, file_id):
#     url = f"{BASE_URL}/vector_stores/{store_id}/file_batches"
#     headers = {
#         "Authorization": f"Bearer {API_KEY}",
#         "Content-Type": "text/html"
#     }
#     data = {
#         "files": [
#             {"id": file_id}
#         ]
#     }
#     response = requests.post(url, headers=headers, json=data)
#     response.raise_for_status()
#     print(f"✅ File attached to Vector Store: {response.json()}")

# if __name__ == "__main__":
#     file_id = upload_file("./calories_database.txt")  # Replace with your file path
#     store_id = create_vector_store()
#     # attach_file_to_vector_store(store_id, file_id)