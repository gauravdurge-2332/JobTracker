from pwdlib import PasswordHash

password_hash = PasswordHash.recommended() 

def hash_Password(password : str) -> str :
    return password_hash.hash(password)

def verifyPassword(password : str , hashed: str) -> bool:
    return password_hash.verify(password, hashed) 