import os 

url = os.getenv("DATABASE_URL") 
print(url)

#postgresql+psycopg://postgres:240906@localhost:5432/authentication