import bcrypt
from db import run_query

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

def authenticate_user(username: str, password: str):
    query = """
        SELECT u.user_id, u.store_id, u.username, u.password_hash, u.role, 
               s.store_name, s.subscription_status, s.expiry_date
        FROM users u
        LEFT JOIN stores s ON u.store_id = s.store_id
        WHERE u.username = :username;
    """
    df = run_query(query, {"username": username})
    if df.empty:
        return None
    
    user = df.iloc[0].to_dict()
    if verify_password(password, user["password_hash"]):
        return user
    return None